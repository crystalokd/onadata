# -*- coding: utf-8 -*-
"""
Celery api.tasks module.
"""
import os
import sys
import logging
from datetime import timedelta

from celery.result import AsyncResult
from django.conf import settings
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.core.files.storage import default_storage
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.datastructures import MultiValueDict

from onadata.apps.api import tools
from onadata.libs.utils.email import send_generic_email
from onadata.libs.utils.model_tools import queryset_iterator
from onadata.apps.logger.models import Instance, ProjectInvitation, XForm
from onadata.libs.utils.email import ProjectInvitationEmail
from onadata.celeryapp import app

User = get_user_model()


def recreate_tmp_file(name, path, mime_type):
    """Creates a TemporaryUploadedFile from a file path with given name"""
    tmp_file = TemporaryUploadedFile(name, mime_type, 0, None)
    # pylint: disable=consider-using-with,unspecified-encoding
    tmp_file.file = open(path)
    tmp_file.size = os.fstat(tmp_file.fileno()).st_size
    return tmp_file


@app.task(bind=True)
def publish_xlsform_async(self, user_id, post_data, owner_id, file_data):
    """Publishes an XLSForm"""
    try:
        files = MultiValueDict()
        files["xls_file"] = default_storage.open(file_data.get("path"))

        owner = User.objects.get(id=owner_id)
        if owner_id == user_id:
            user = owner
        else:
            user = User.objects.get(id=user_id)
        survey = tools.do_publish_xlsform(user, post_data, files, owner)
        default_storage.delete(file_data.get("path"))

        if isinstance(survey, XForm):
            return {"pk": survey.pk}

        return survey
    except Exception as exc:  # pylint: disable=broad-except
        if isinstance(exc, MemoryError):
            if self.request.retries < 3:
                self.retry(exc=exc, countdown=1)
            else:
                error_message = (
                    "Service temporarily unavailable, please try to "
                    "publish the form again"
                )
        else:
            error_message = str(sys.exc_info()[1])

        return {"error": error_message}


@app.task()
def delete_xform_async(xform_id, user_id):
    """Soft delete an XForm asynchrounous task"""
    xform = XForm.objects.get(pk=xform_id)
    user = User.objects.get(pk=user_id)
    xform.soft_delete(user)


@app.task()
def delete_user_async():
    """Delete inactive user accounts"""
    users = User.objects.filter(
        active=False, username__contains="deleted-at", email__contains="deleted-at"
    )
    for user in users:
        user.delete()


def get_async_status(job_uuid):
    """Gets progress status or result"""

    if not job_uuid:
        return {"error": "Empty job uuid"}

    job = AsyncResult(job_uuid)
    result = job.result or job.state
    if isinstance(result, str):
        return {"JOB_STATUS": result}

    return result


@app.task()
def send_verification_email(email, message_txt, subject):
    """
    Sends a verification email
    """
    send_generic_email(email, message_txt, subject)


@app.task()
def send_account_lockout_email(email, message_txt, subject):
    """Sends account locked email."""
    send_generic_email(email, message_txt, subject)


@app.task()
def delete_inactive_submissions():
    """
    Task to periodically delete soft deleted submissions from db
    """
    submissions_lifespan = getattr(settings, "INACTIVE_SUBMISSIONS_LIFESPAN", None)
    if submissions_lifespan:
        time_threshold = timezone.now() - timedelta(days=submissions_lifespan)
        # delete instance attachments
        instances = Instance.objects.filter(
            deleted_at__isnull=False, deleted_at__lte=time_threshold
        )
        for instance in queryset_iterator(instances):
            # delete submission
            instance.delete()


@app.task()
def send_project_invitation_email_async(
    invitation_id: str, url: str
):  # pylint: disable=invalid-name
    """Sends project invitation email asynchronously"""
    try:
        invitation = ProjectInvitation.objects.get(id=invitation_id)

    except ProjectInvitation.DoesNotExist as err:
        logging.exception(err)

    else:
        email = ProjectInvitationEmail(invitation, url)
        email.send()

# Copyright 2018 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import psycopg2
from odoo import api, fields, models
from odoo.addons.queue_job.job import job, DEFAULT_PRIORITY


class MailMail(models.Model):
    _inherit = 'mail.mail'

    mail_job_priority = fields.Integer(
        oldname='priority',
        default=DEFAULT_PRIORITY,
        help="Send the email with a priority level.\n"
             "0 being the higher priority. Default is %d" % DEFAULT_PRIORITY,
    )

    @api.multi
    @job(default_channel='root.mail')
    def _send_mail_jobified(self):
        """
        Send the email if
        - the state is 'outgoing'
        - the mail is not processing by another job (locked)
        - the mail exists.
        :return: str
        """
        # Make sure two jobs don't send the same email.
        # Use the NOWAIT because if the mail is already locked, it's because
        # another process is using it to send the e-mail.
        # And when the record'll be unlocked, we'll send it again.
        self.ensure_one()
        query = """
        SELECT id
        FROM mail_mail
        WHERE id = %s
        FOR UPDATE NOWAIT;
        """
        try:
            self.env.cr.execute(query, (self.id,))
        except psycopg2.OperationalError:
            return "mail.mail record (id=%d) already in processing" % self.id
        if not self.exists():
            return "mail.mail record (id=%d) no longer exists" % self.id
        elif self.state != 'outgoing':
            return "Not in Outgoing state, ignoring"
        self.send(auto_commit=False, raise_exception=True)
        return ""

    @api.multi
    def _send_email_delay(self, operation='write'):
        """
        Execute the _send_mail_jobified function with the priority defined
        into the mail.mail (self) and a description depending on the
        operation.
        This function split given records to create one job queue per mail.
        :param records: mail.mail recordset
        :param operation: str
        :return: None
        """
        mails_outgoing = self.filtered(lambda m: m.state == 'outgoing')
        if mails_outgoing:
            description = "Delayed email send (operation: %s)" % operation
            # Loop to create 1 job per mail.mail
            for mail_outgoing in mails_outgoing:
                mail_outgoing.with_delay(
                    priority=mail_outgoing.mail_job_priority,
                    description=description)._send_mail_jobified()

    @api.model
    def create(self, vals):
        """
        Overwrite to send the mail using queue job
        :param vals: dict
        :return: self recordset
        """
        result = super(MailMail, self).create(vals)
        result._send_email_delay(operation='create')
        return result

    @api.multi
    def write(self, vals):
        """
        Overwrite to send the mail using queue job
        :param vals: dict
        :return: bool
        """
        result = super(MailMail, self).write(vals)
        self._send_email_delay(operation='write')
        return result

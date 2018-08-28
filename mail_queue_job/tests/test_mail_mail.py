# Copyright 2018 ACSONE SA/NV (<http://acsone.eu>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
import mock
from odoo import fields
from odoo.tests.common import TransactionCase
from odoo.addons.queue_job.job import Job


class TestMailMail(TransactionCase):
    """
    Tests for mail.mail
    Note: we can't test the case of the mail.mail locked
    (into function _send_mail_jobified()) because if we create a new cursor,
    it'll have another transaction (so the mail.mail doesn't exist).
    And the lock is done by cursor; So queue job (with same cursor) will have
    access to the record.
    """

    def setUp(self):
        super().setUp()
        self.mail_obj = self.env['mail.mail']
        self.partner = self.env.ref("base.res_partner_2")
        self.queue_obj = self.env['queue.job']
        self.job_fct = "_send_mail_jobified"
        self.prepare_job_fct = "_send_email_delay"
        self.job_path = "odoo.addons.mail_queue_job.models." \
                        "mail_mail.MailMail.%s" % self.job_fct
        self.prepare_job_path = "odoo.addons.mail_queue_job.models." \
                                "mail_mail.MailMail.%s" % self.prepare_job_fct
        self.description = "Delayed email send %"

    def _get_related_jobs(self, existing_jobs, mail, now):
        """

        :param existing_jobs: queue.job recordset
        :param mail: mail.mail recordset
        :param now: date (str)
        :return: queue.job recordset
        """
        new_jobs = self.queue_obj.search([
            ('id', 'not in', existing_jobs.ids),
            ('model_name', '=', mail._name),
            ('method_name', '=', self.job_fct),
            ('priority', '=', mail.mail_job_priority),
            ('name', 'ilike', self.description),
            ('date_created', '>=', now),
        ])
        return new_jobs

    def _execute_real_job(self, queue_job):
        """
        Load and execute the given queue_job.
        Also refresh the queue_job to have updated fields
        :param queue_job: queue.job recordset
        :return: Job object
        """
        real_job = Job.load(queue_job.env, queue_job.uuid)
        real_job.perform()
        real_job.set_done()
        real_job.store()
        queue_job.refresh()
        return real_job

    def test_notify_creation(self):
        """
        Test if during the creation of a new mail.mail recordset,
        the notify is correctly triggered and pass into the
        listener on_record_create().
        :return:
        """
        values = {
            'subject': 'Unit test',
            'body_html': '<p>Test</p>',
            'email_to': 'test@example.com',
            'state': 'outgoing',
            'partner_ids': [(4, self.partner.id, False)],
        }
        with mock.patch(self.job_path, autospec=True) as magic:
            magic.delayable = True
            existing_jobs = self.queue_obj.search([])
            now = fields.Datetime.now()
            mail = self.mail_obj.create(values)
            new_job = self._get_related_jobs(existing_jobs, mail, now)
            self.assertEquals(len(new_job), 1)
            self._execute_real_job(new_job)
            self.assertEquals(new_job.state, 'done')
            self.assertEqual(magic.call_count, 1)

    def test_notify_creation_skipped(self):
        """
        Test if during the creation of a new mail.mail recordset,
        the notify is not triggered and don't pass into the
        listener on_record_create().
        Skipped due to the state who is not 'outgoing'.
        :return:
        """
        values = {
            'subject': 'Unit test',
            'body_html': '<p>Test</p>',
            'email_to': 'test@example.com',
            'partner_ids': [(4, self.partner.id, False)],
            'state': 'cancel',
        }
        with mock.patch(self.prepare_job_path, autospec=True) as magic:
            magic.delayable = True
            existing_jobs = self.queue_obj.search([])
            now = fields.Datetime.now()
            mail = self.mail_obj.create(values)
            new_job = self._get_related_jobs(existing_jobs, mail, now)
            self.assertEquals(len(new_job), 0)
            self.assertEqual(magic.call_count, 1)

    def test_notify_write(self):
        """
        Test if during the creation of a new mail.mail recordset,
        the notify is correctly triggered and pass into the
        listener on_record_write().
        :return:
        """
        values = {
            'subject': 'Unit test',
            'body_html': '<p>Test</p>',
            'email_to': 'test@example.com',
            'partner_ids': [(4, self.partner.id, False)],
            'state': 'outgoing',
        }
        mail = self.mail_obj.create(values)
        with mock.patch(self.job_path, autospec=True) as magic:
            magic.delayable = True
            existing_jobs = self.queue_obj.search([])
            now = fields.Datetime.now()
            mail.write({
                'subject': 'another subject',
            })
            new_job = self._get_related_jobs(existing_jobs, mail, now)
            self.assertEquals(len(new_job), 1)
            self._execute_real_job(new_job)
            self.assertEquals(new_job.state, 'done')
            self.assertEqual(magic.call_count, 1)

    def test_notify_write_skipped(self):
        """
        Test if during the creation of a new mail.mail recordset,
        the notify is not triggered and don't pass into the
        listener on_record_write().
        Skipped due to the state who is not 'outgoing'.
        :return:
        """
        values = {
            'subject': 'Unit test',
            'body_html': '<p>Test</p>',
            'email_to': 'test@example.com',
            'partner_ids': [(4, self.partner.id, False)],
            'state': 'cancel',
        }
        mail = self.mail_obj.create(values)
        with mock.patch(self.prepare_job_path, autospec=True) as magic:
            magic.delayable = True
            existing_jobs = self.queue_obj.search([])
            now = fields.Datetime.now()
            mail.write({
                'subject': 'another subject',
            })
            new_job = self._get_related_jobs(existing_jobs, mail, now)
            self.assertEquals(len(new_job), 0)
            self.assertEqual(magic.call_count, 1)

    def test_job_during_create(self):
        """
        Test if during the creation of a mail.mail, a job is correctly
        triggered with the correct priority and correct description
        :return:
        """
        priority = 25
        values = {
            'subject': 'Unit test',
            'body_html': '<p>Test</p>',
            'email_to': 'test@example.com',
            'partner_ids': [(4, self.partner.id, False)],
            'state': 'outgoing',
            'mail_job_priority': priority,
        }
        existing_jobs = self.queue_obj.search([])
        now = fields.Datetime.now()
        mail = self.mail_obj.create(values)
        # Ensure the priority is correct before continue
        self.assertEquals(mail.mail_job_priority, priority)
        new_jobs = self._get_related_jobs(existing_jobs, mail, now)
        self.assertEquals(len(new_jobs), 1)

    def test_job_during_create_skipped(self):
        """
        Test if during the creation of a mail.mail, a job is not
        triggered/created (because the state of the mail.mail is not
        'outgoing'.
        :return:
        """
        priority = 25
        values = {
            'subject': 'Unit test',
            'body_html': '<p>Test</p>',
            'email_to': 'test@example.com',
            'partner_ids': [(4, self.partner.id, False)],
            'state': 'cancel',
            'mail_job_priority': priority,
        }
        existing_jobs = self.queue_obj.search([])
        now = fields.Datetime.now()
        mail = self.mail_obj.create(values)
        # Ensure the priority is correct before continue
        self.assertEquals(mail.mail_job_priority, priority)
        new_jobs = self._get_related_jobs(existing_jobs, mail, now)
        self.assertEquals(len(new_jobs), 0)

    def test_mail_no_exists(self):
        """
        Test the queue job when the mail.mail doesn't exists
        :return:
        """
        values = {
            'subject': 'Unit test',
            'body_html': '<p>Test</p>',
            'email_to': 'test@example.com',
            'partner_ids': [(4, self.partner.id, False)],
            'state': 'outgoing',
            'mail_job_priority': 20,
        }
        existing_jobs = self.queue_obj.search([])
        now = fields.Datetime.now()
        mail = self.mail_obj.create(values)
        new_job = self._get_related_jobs(existing_jobs, mail, now)
        new_job.write({
            'record_ids': [mail.id + 1000],
        })
        self.assertEquals(len(new_job), 1)
        self._execute_real_job(new_job)
        self.assertFalse(bool(new_job.exc_info))
        self.assertEquals(new_job.state, 'done')
        return

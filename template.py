# -*- coding: UTF-8 -*-
# This file is part electronic_mail_template module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
"Email Template"
from __future__ import with_statement

import mimetypes
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.utils import formatdate
from email import Encoders
from email.header import decode_header

from genshi.template import TextTemplate
from trytond.model import ModelView, ModelSQL, fields
from trytond.tools import safe_eval
from trytond.transaction import Transaction
from trytond.pyson import Eval
from trytond.pool import Pool
try:
    from jinja2 import Template as Jinja2Template
    jinja2_loaded = True
except ImportError:
    jinja2_loaded = False
    logging.getLogger('electronic_mail_template').error(
        'Unable to import jinja2. Install jinja2 package.')


def split_emails(emails):
    """Email IDs could be separated by ';' or ','

    >>> email_list = '1@x.com;2@y.com , 3@z.com '
    >>> emails = split_emails(email_list)
    >>> emails
    ['1@x.com', '2@y.com', '3@z.com']

    :param email_ids: email id
    :type email_ids: str or unicode
    """
    if not emails:
        return []
    emails = emails.replace(' ', '').replace(',', ';')
    return emails.split(';')


def recipients_from_fields(email_record):
    """
    Returns a list of email addresses who are the recipients of this email

    :param email_record: Browse record of the email
    """
    recipients = []
    for field in ('to', 'cc', 'bcc'):
        recipients.extend(split_emails(getattr(email_record, field)))
    return recipients

__all__ = ['Template', 'TemplateReport']


class Template(ModelSQL, ModelView):
    'Email Template'
    __name__ = 'electronic.mail.template'

    from_ = fields.Char('From')
    sender = fields.Char('Sender')
    to = fields.Char('To')
    cc = fields.Char('CC')
    bcc = fields.Char('BCC')
    subject = fields.Char('Subject', translate=True)
    smtp_server = fields.Many2One('smtp.server', 'SMTP Server',
        domain=[('state', '=', 'done')], required=True)
    name = fields.Char('Name', required=True, translate=True)
    model = fields.Many2One('ir.model', 'Model', required=True)
    mailbox = fields.Many2One('electronic.mail.mailbox', 'Mailbox', required=True)
    draft_mailbox = fields.Many2One('electronic.mail.mailbox', 'Draft Mailbox', required=True)
    language = fields.Char('Language', help='Expression to find the ISO langauge code')
    plain = fields.Text('Plain Text Body', translate=True)
    html = fields.Text('HTML Body', translate=True)
    reports = fields.Many2Many('electronic.mail.template.ir.action.report',
        'template', 'report', 'Reports')
    engine = fields.Selection('get_engines', 'Engine', required=True)
    triggers = fields.One2Many(
        'ir.trigger', 'email_template', 'Triggers',
        context={
            'model': Eval('model'),
            'email_template': True,
            })
    signature = fields.Boolean('Use Signature', help='The signature from the User details '
        'will be appened to the mail.')
    message_id = fields.Char('Message-ID', help='Unique Message Identifier')
    in_reply_to = fields.Char('In Repply To')
    create_message_id = fields.Boolean('Message ID',
        help='Generate Message ID when send email')

    @classmethod
    def __setup__(cls):
        super(Template, cls).__setup__()
        cls._error_messages.update({
                'smtp_error': 'Wrong connection to SMTP server. Email have not sent',
                'recipients_error': 'Not valid recipients emails. Check emails in To, Cc or Bcc',
                'smtp_server_default': 'There are not default SMTP server',
                })

    @staticmethod
    def default_template():
        return True

    @staticmethod
    def default_engine():
        '''Default Engine'''
        return 'genshi'

    @classmethod
    def get_engines(cls):
        '''Returns the engines as list of tuple

        :return: List of tuples
        '''
        engines = [
            ('python', 'Python'),
            ('genshi', 'Genshi'),
            ]
        if jinja2_loaded:
            engines.append(('jinja2', 'Jinja2'))
        return engines

    @classmethod
    def check_xml_record(cls, records, values):
        '''It should be possible to overwrite templates'''
        return True

    def eval(self, expression, record):
        '''Evaluates the given :attr:expression

        :param expression: Expression to evaluate
        :param record: The browse record of the record
        '''
        engine_method = getattr(self, '_engine_' + self.engine)
        return engine_method(expression, record)

    @staticmethod
    def template_context(record):
        """Generate the tempalte context

        This is mainly to assist in the inheritance pattern
        """
        return {'record': record}

    @classmethod
    def _engine_python(cls, expression, record):
        '''Evaluate the pythonic expression and return its value
        '''
        if expression is None:
            return u''

        assert record is not None, 'Record is undefined'
        template_context = cls.template_context(record)
        return safe_eval(expression, template_context)

    @classmethod
    def _engine_genshi(cls, expression, record):
        '''
        :param expression: Expression to evaluate
        :param record: Browse record
        '''
        if not expression:
            return u''

        template = TextTemplate(expression)
        template_context = cls.template_context(record)
        return template.generate(**template_context).render(encoding='UTF-8')

    @classmethod
    def _engine_jinja2(cls, expression, record):
        '''
        :param expression: Expression to evaluate
        :param record: Browse record
        '''
        if not jinja2_loaded or not expression:
            return u''

        template = Jinja2Template(expression)
        template_context = cls.template_context(record)
        return template.render(template_context).encode('utf-8')

    @classmethod
    def render(cls, template, record):
        '''Renders the template and returns as email object
        :param template: Browse Record of the template
        :param record: Browse Record of the record on which the template
            is to generate the data on
        :return: 'email.message.Message' instance
        '''

        message = MIMEMultipart()
        message['date'] = formatdate(localtime=1)

        language = Transaction().context.get('language', 'en_US')
        if template.language:
            language = template.eval(template.language, record)

        with Transaction().set_context(language=language):
            template = cls(template.id)

            # Simple rendering fields
            simple_fields = {
                'from_': 'from',
                'sender': 'sender',
                'to': 'to',
                'cc': 'cc',
                #~ 'bcc': 'bcc',
                'subject': 'subject',
                'message_id': 'message-id',
                'in_reply_to': 'in-reply-to',
                }
            for field_name in simple_fields.keys():
                field_expression = getattr(template, field_name)
                eval_result = template.eval(field_expression, record)
                if eval_result:
                    message[simple_fields[field_name]] = eval_result

            # Attach reports
            if template.reports:
                reports = cls.render_reports(template, record)
                for report in reports:
                    ext, data, filename, file_name = report[0:5]
                    if file_name:
                        filename = template.eval(file_name, record)
                    filename = ext and '%s.%s' % (filename, ext) or filename
                    content_type, _ = mimetypes.guess_type(filename)
                    maintype, subtype = (
                        content_type or 'application/octet-stream'
                        ).split('/', 1)

                    attachment = MIMEBase(maintype, subtype)
                    attachment.set_payload(data)
                    Encoders.encode_base64(attachment)
                    attachment.add_header(
                        'Content-Disposition', 'attachment', filename=filename)
                    attachment.add_header(
                        'Content-Transfer-Encoding', 'base64')
                    message.attach(attachment)

            # HTML & Text Alternate parts
            plain = template.eval(template.plain, record)
            html = template.eval(template.html, record)
            if template.signature:
                User = Pool().get('res.user')
                user = User(Transaction().user)
                if user.signature_html:
                    signature = user.signature_html.encode("utf8")
                    html = '%s<br>--<br>%s' % (html, signature)
                if user.signature:
                    signature = user.signature.encode("utf-8")
                    plain = '%s\n--\n%s' % (plain, signature)
                    if not user.signature_html:
                        html = '%s<br>--<br>%s' % (html,
                            signature.replace('\n', '<br>'))
            body = MIMEMultipart('alternative')
            body.attach(MIMEText(plain, _charset='utf-8'))
            body.attach(MIMEText(html, 'html', _charset='utf-8'))
            message.attach(body)

        return message

    @classmethod
    def render_reports(cls, template, record):
        '''Renders the reports and returns as a list of tuple

        :param template: Browse Record of the template
        :param record: Browse Record of the record on which the template
            is to generate the data on
        :return: List of tuples with:
            report_type
            data
            the report name
            the report file name (optional)
        '''
        reports = []
        for report_action in template.reports:
            report = Pool().get(report_action.report_name, type='report')
            reports.append([report.execute([record.id], {'id': record.id}),
                report_action.file_name])

        # The boolean for direct print in the tuple is useless for emails
        return [(r[0][0], r[0][1], r[0][3], r[1]) for r in reports]

    @classmethod
    def render_and_send(cls, template_id, records):
        """
        Render the template and send
        :param template_id: ID template
        :param records: List Object of the records
        """
        template = cls(template_id)
        ElectronicMail = Pool().get('electronic.mail')
        for record in records:
            email_message = cls.render(template, record)

            context = {}
            field_expression = getattr(template, 'bcc')
            eval_result = template.eval(field_expression, record)
            if eval_result:
                context['bcc'] = eval_result

            electronic_email = ElectronicMail.create_from_email(
                email_message, template.mailbox.id, context)
            cls.send_email(electronic_email, template)
            cls.add_event(template, record, electronic_email, email_message)  # add event
        return True

    @classmethod
    def mail_from_trigger(cls, records, trigger_id):
        """
        To be used with ir.trigger to send mails automatically

        The process involves identifying the tempalte which needs
        to be pulled when the trigger is.

        :param records: Object of the records
        :param trigger_id: ID of the trigger
        """
        Trigger = Pool().get('ir.trigger')
        trigger = Trigger(trigger_id)
        return cls.render_and_send(trigger.email_template.id, records)

    @classmethod
    def send_email(cls, email_id, template=False):
        """
        Send out the given email using the SMTP_CLIENT if configured in the
        Tryton Server configuration

        :param email_id: ID of the email to be sent
        :param template: Browse Record of the template
        """
        ElectronicMail = Pool().get('electronic.mail')
        SMTP = Pool().get('smtp.server')

        email = ElectronicMail(email_id)
        recipients = recipients_from_fields(email)

        """SMTP Server from template or default"""
        if not template:
            servers = SMTP.search([
                    ('state','=','done'),
                    ('default','=',True),
                    ])
            if not len(servers)>0:
                cls.raise_user_error('smtp_server_default')
        server = template and template.smtp_server or servers[0]

        """Validate recipients to send or move email to draft mailbox"""
        emails = ",".join(recipients)
        if not ElectronicMail.validate_emails(emails.split(',')) and template:
            """Draft Mailbox. Not send email"""
            ElectronicMail.write([email], {
                'mailbox': template.draft_mailbox,
                })
            return False

        try:
            server = SMTP.get_smtp_server(server)
            server.sendmail(email.from_, recipients,
                ElectronicMail._get_email(email))
            server.quit()
            ElectronicMail.write([email], {
                'flag_send': True,
                })
        except:
            cls.raise_user_error('smtp_error')
        return True

    @classmethod
    def add_event(cls, template, record, electronic_email, email_message):
        """
        Add event if party_event is installed
        :param template: Browse Record of the template
        :param record: Browse record of the record
        :param electronic_email: Browse record email to send
        :param email_message: Data email to extract values
        """
        cursor = Transaction().cursor
        cursor.execute(
            "SELECT state "
            "from ir_module_module "
            "where state='installed' and name = 'party_event'")
        party_event = cursor.fetchall()
        if party_event and template.party:
            party = template.eval(template.party, record)
            resource = 'electronic.mail,%s' % electronic_email.id
            values = {
                'subject': decode_header(email_message.get('subject'))[0][0],
                'description': electronic_email.body_plain,
                }
            Pool().get('party.event').create_event(party, resource, values)
        return True


class TemplateReport(ModelSQL):
    'Template - Report Action'
    __name__ = 'electronic.mail.template.ir.action.report'

    template = fields.Many2One('electronic.mail.template', 'Template')
    report = fields.Many2One('ir.action.report', 'Report')

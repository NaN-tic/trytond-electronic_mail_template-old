# -*- coding: UTF-8 -*-
# This file is part electronic_mail_template module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from __future__ import with_statement
from os import path, listdir
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.utils import formatdate
from email import Encoders, charset
from genshi.template import TextTemplate
from trytond import backend
from trytond.model import ModelView, ModelSQL, fields
from trytond.transaction import Transaction
from trytond.pyson import Eval
from trytond.pool import Pool
import mimetypes
import logging

logger = logging.getLogger(__name__)

try:
    from jinja2 import Template as Jinja2Template
    jinja2_loaded = True
except ImportError:
    jinja2_loaded = False
    logger.error('Unable to import jinja2. Install jinja2 package.')

__all__ = ['Template', 'TemplateReport']

def styles_dir():
    return '%s/styles/' % (path.dirname(path.realpath(__file__)))


class Template(ModelSQL, ModelView):
    'Email Template'
    __name__ = 'electronic.mail.template'

    from_ = fields.Char('From')
    sender = fields.Char('Sender')
    to = fields.Char('To')
    cc = fields.Char('CC')
    bcc = fields.Char('BCC')
    reply_to = fields.Char('Reply To')
    subject = fields.Char('Subject', translate=True)
    name = fields.Char('Name', required=True, translate=True)
    model = fields.Many2One('ir.model', 'Model', required=True)
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
    in_reply_to = fields.Char('In Reply To')
    queue = fields.Boolean('Queue',
        help='Put these messages in the output mailbox instead of sending '
            'them immediately.')
    mailbox = fields.Many2One('electronic.mail.mailbox', 'Mailbox',
        help='Mailbox send mail')
    mailbox_outbox = fields.Many2One('electronic.mail.mailbox', 'Outbox Mailbox',
        help='Mailbox outbox to send mail')
    style = fields.Selection('get_style', 'Style',
        help='HTML CSS style')
    custom_style = fields.Text('Custom Style',
        help='Custom HTML CSS style')
    activity = fields.Char('Activity',
        help='Generate a new activity record related a party:\n' \
            '${record.party.id}')

    @classmethod
    def __setup__(cls):
        super(Template, cls).__setup__()
        cls._error_messages.update({
                'recipients_error': 'Not valid recipients emails. Check emails in To, Cc or Bcc',
                })

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        table = TableHandler(cursor, cls, module_name)

        # Migration from 3.6: change party to activity field
        if (table.column_exist('party')):
            table.column_rename('party', 'activity')

        super(Template, cls).__register__(module_name)

        # Migration from 3.2: drop required on mailbox and draft_mailbox
        table.not_null_action('mailbox', action='remove')
        if (table.column_exist('draft_mailbox')):
            table.not_null_action('draft_mailbox', action='remove')
        if (table.column_exist('smtp_server')):
            table.not_null_action('smtp_server', action='remove')

    @classmethod
    def check_xml_record(cls, records, values):
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
    def get_style(cls):
        styles = [(None, '')]
        for s in listdir(styles_dir()):
            styles.append((s, s[:-4].capitalize()))
        return styles

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
        return eval(expression, template_context)

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

    def render(self, record):
        '''Renders the template and returns as email object
        :param record: Browse Record of the record on which the template
            is to generate the data on
        :return: 'email.message.Message' instance
        '''

        message = MIMEMultipart()
        message['date'] = formatdate(localtime=1)

        language = Transaction().context.get('language', 'en_US')
        if self.language:
            language = self.eval(self.language, record)

        with Transaction().set_context(language=language):

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
                field_expression = getattr(self, field_name)
                eval_result = self.eval(field_expression, record)
                if eval_result:
                    message[simple_fields[field_name]] = eval_result

            if self.reply_to:
                eval_result = self.eval(self.reply_to, record)
                if eval_result:
                    message['reply-to'] = eval_result

            # Attach reports
            if self.reports:
                reports = self.render_reports(record)
                for report in reports:
                    ext, data, filename, file_name = report[0:5]
                    if file_name:
                        filename = self.eval(file_name, record)
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
            plain = self.eval(self.plain, record)
            html = self.eval(self.html, record)
            if self.signature:
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

            style = ''
            if self.style:
                fname = '%s/%s' % (styles_dir(), self.style)
                with open(fname) as f:
                    style = f.read()
                if self.custom_style:
                    style += '\n%s' % self.custom_style
            elif self.custom_style:
                style = '%s' % self.custom_style

            html = """
                <html>
                <head><head>
                <style>
                %s
                </style>
                <body>
                %s
                </body>
                </html>
                """ % (style, html)

            body = MIMEMultipart('alternative')
            charset.add_charset('utf-8', charset.QP, charset.QP)
            body.attach(MIMEText(plain, _charset='utf-8'))
            body.attach(MIMEText(html, 'html', _charset='utf-8'))
            message.attach(body)

        return message

    def render_reports(self, record):
        '''Renders the reports and returns as a list of tuple

        :param record: Browse Record of the record on which the template
            is to generate the data on
        :return: List of tuples with:
            report_type
            data
            the report name
            the report file name (optional)
        '''
        reports = []
        for report_action in self.reports:
            report = Pool().get(report_action.report_name, type='report')
            reports.append([report.execute([record.id], {'id': record.id}),
                report_action.file_name])

        # The boolean for direct print in the tuple is useless for emails
        return [(r[0][0], r[0][1], r[0][3], r[1]) for r in reports]

    def render_and_send(self, records):
        """
        Render the template and send
        :param records: List Object of the records
        """
        pool = Pool()
        ElectronicMail = pool.get('electronic.mail')
        EmailConfiguration = pool.get('electronic.mail.configuration')

        activities = []
        for record in records:
            email_message = self.render(record)

            context = {}
            field_expression = getattr(self, 'bcc')
            eval_result = self.eval(field_expression, record)
            if eval_result:
                context['bcc'] = eval_result
            email_configuration = EmailConfiguration(1)
            if self.queue:
                mailbox = self.mailbox_outbox \
                    if self.mailbox_outbox else email_configuration.outbox
            else:
                mailbox = self.mailbox if self.mailbox \
                    else email_configuration.sent

            electronic_email = ElectronicMail.create_from_email(
                email_message, mailbox, context)
            if not electronic_email: # not configured mailbox
                return
            if not self.queue:
                electronic_email.send_email()
                logger.info('Send email: %s' %
                    (electronic_email.rec_name))
                activities.append({
                    'record': record,
                    'template': self,
                    'mail': electronic_email,
                    })

        if activities:
            self.add_activities(activities)  # add activities
        return

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
        return trigger.email_template.render_and_send(records)

    @classmethod
    def add_activities(cls, records):
        """
        Add activities related to party
        :param records: {'record', 'template', 'mail'}
        """
        cursor = Transaction().cursor
        cursor.execute(
            "SELECT state "
            "from ir_module "
            "where state='installed' and name = 'activity'")
        activity_installed = cursor.fetchall()
        if not activity_installed:
            return

        pool = Pool()
        Activity = pool.get('activity.activity')
        ActivityType = pool.get('activity.type')
        ActivityReference = pool.get('activity.reference')
        ModelData = pool.get('ir.model.data')
        Party = pool.get('party.party')

        type_id = ActivityType(ModelData.get_id(
            'activity', 'outgoing_email_type'))

        activities = []
        for r in records:
            record = r['record']
            template = r['template']
            mail = r['mail']

            if template.activity:
                activity = Activity()
                activity.activity_type = type_id
                activity.subject = mail.subject
                activity.description = mail.body_plain
                activity.state = 'held'

                party = template.eval(template.activity, record)
                if party:
                    activity.party = Party(party)

                resources = ActivityReference.search([
                    ('model', '=', template.model)
                    ])
                if resources:
                    resource, = resources
                    activity.resource = '%s,%s' % (
                        resource.model.model,
                        record.id)

                activities.append(activity)

        if activities:
            Activity.save(activities)

    def get_attachments(self, records):
        record_ids = [r.id for r in records]
        attachments = []
        for report in self.reports:
            report = Pool().get(report.report_name, type='report')
            ext, data, filename, file_name = report.execute(record_ids, {})

            if file_name:
                filename = self.eval(file_name, record_ids).decode('utf-8')
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
            attachments.append(attachment)
        return attachments


class TemplateReport(ModelSQL):
    'Template - Report Action'
    __name__ = 'electronic.mail.template.ir.action.report'

    template = fields.Many2One('electronic.mail.template', 'Template')
    report = fields.Many2One('ir.action.report', 'Report')

    @classmethod
    def check_xml_record(cls, records, values):
        return True

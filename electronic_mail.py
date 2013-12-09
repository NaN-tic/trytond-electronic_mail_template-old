# -*- coding: UTF-8 -*-
#This file is part electronic_mail_template module for Tryton.
#The COPYRIGHT file at the top level of this repository contains 
#the full copyright notices and license terms.
from email import message_from_string
from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import Pool
from trytond.pyson import Eval
import base64

__all__ = ['ElectronicMail']


class ElectronicMail(ModelSQL, ModelView):
    "E-Mail module extended to suit inbuilt reading and templating"
    __name__ = 'electronic.mail'

    subject = fields.Char('Subject', translate=True)
    body_html = fields.Function(
        fields.Text('HTML (BODY)'), 'get_email_body')
    body_plain = fields.Function(
        fields.Text('Plain Text (BODY)'), 'get_email_body')

    @classmethod
    def __setup__(cls):
        super(ElectronicMail, cls).__setup__()
        cls._buttons.update({
                'send_mail': {
                    'invisible': Eval('body_plain') == '',
                    },
                })

    def get_email_body(self, name):
        """Returns the email body
        """
        result = ''
        message = message_from_string(self._get_email(self))
        for part in message.walk():
            content_type = part.get_content_type()
            if content_type == 'text/plain':
                result = base64.b64decode(part.get_payload())
        return result

    @classmethod
    def check_xml_record(cls, records, values):
        '''It should be possible to overwrite templates'''
        return True

    @classmethod
    @ModelView.button
    def send_mail(self, emails):
        Template = Pool().get('electronic.mail.template')
        for email in emails:
            Template.send_email(email)

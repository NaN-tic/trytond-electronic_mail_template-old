#This file is part electronic_mail_template module for Tryton.
#The COPYRIGHT file at the top level of this repository contains 
#the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields


class ActionReport(ModelSQL, ModelView):
    "Action report"
    _name = 'ir.action.report'

    file_name = fields.Char('File Name Pattern', translate=True, 
        help='File name e-mail attachment without extension. eg. sale_${record.reference}')

ActionReport()

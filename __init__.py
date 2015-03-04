# -*- coding: UTF-8 -*-
# This file is part electronic_mail_template module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pool import Pool
from .template import *
from .trigger import *
from .report import *

def register():
    Pool.register(
        ActionReport,
        Template,
        TemplateReport,
        Trigger,
        module='electronic_mail_template', type_='model')

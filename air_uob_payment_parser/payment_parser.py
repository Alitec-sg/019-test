# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

from odoo.exceptions import UserError, RedirectWarning, ValidationError


class ResBank(models.Model):
    _inherit = "res.bank"

    bank_uob = fields.Boolean('UOB', default=False)
    
    
    
class BankFileAttachment(models.Model):
    _name = 'bank.file.attachment'
    
    name = fields.Char('Name')
    attachment_id = fields.Many2one('ir.attachment','Attachment')
    file_date = fields.Date('Date',default=fields.Date.today())
    invoice_ids = fields.Many2many('account.invoice','invoice_bnk_attachment_rel','attach_id','invoice_id',string="Invoices")
    datas = fields.Binary(related="attachment_id.datas", string="Bank File")
    datas_fname = fields.Char(related="attachment_id.datas_fname", string="Bank File Name")
    type = fields.Selection(selection=[('url','URL'),('binary','Binary')], related="attachment_id.type", string="Type")
    index_content = fields.Text(related="attachment_id.index_content", string="Index Content")
    bank_file_type = fields.Selection(selection=[('uob','UOB'),('cimb','CIMB')], string=" Bank Type", default='uob')

class account_payment(models.Model):
    _inherit = "account.payment"

    @api.multi
    def post(self):
        """ Posts a payment used to pay an invoice. This function only posts the
        payment by default but can be overridden to apply specific post or pre-processing.
        It is called by the "validate" button of the popup window
        triggered on invoice form by the "Register Payment" button.
        """
#         if any(len(record.invoice_ids) != 1 for record in self):
#             # For multiple invoices, there is account.register.payments wizard
#             raise UserError(_("This method should only be called to process a single invoice's payment."))
        for payment in self:
            if payment.payment_method_code == 'manual' and payment.payment_type =='outbound' and payment.journal_id.type=='bank':
                generate_uob_obj = self.env['generate.uob.files.wiz']
                res = generate_uob_obj.new().do_generate(payment.journal_id)
                super_res = super(account_payment, self).post()
                return res 
            else:
                return super(account_payment, self).post()



class ResPartner(models.Model):
    _inherit = 'res.partner'
 
    is_giro_payment = fields.Boolean("Giro Payment", default=False)
    

class AccountInvoice(models.Model):
    _inherit = 'account.invoice'
 
    is_giro_payment = fields.Boolean(related="partner_id.is_giro_payment", string="Giro Payment", default=False)
    

# 
#     @api.multi
#     def _compute_uob_bank_count(self):
#         partner_bank_obj = self.env['res.partner.bank']
#         for partner in self:
#             bank_ids = partner_bank_obj.search([('partner_id','=', partner.id)])
#             count = 0
#             for bank in bank_ids:
#                 if bank.bank_id and bank.bank_id.bank_uob:
#                     count += 1
#             partner.bank_uob_account_count = count
            
            
            
            
            
#             count_bank_acc = len(bank_ids.mapped('bank_id.bank_uob'))
#             print ("partner.....",partner.name)
#             print (".....Bank_ids...",count_bank_acc)
#         bank_data = self.env['res.partner.bank'].read_group([('partner_id', 'in', self.ids)], ['partner_id'], ['partner_id'])
#         mapped_data = dict([(bank['partner_id'][0], bank['partner_id_count']) if bank.for bank in bank_data])

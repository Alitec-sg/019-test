# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, RedirectWarning, ValidationError
import tempfile
import time
import base64
from collections import defaultdict

MAP_INVOICE_TYPE_PARTNER_TYPE = {
    'out_invoice': 'customer',
    'out_refund': 'customer',
    'in_invoice': 'supplier',
    'in_refund': 'supplier',
}
# Since invoice amounts are unsigned, this is how we know if money comes in or goes out
MAP_INVOICE_TYPE_PAYMENT_SIGN = {
    'out_invoice': 1,
    'in_refund': 1,
    'in_invoice': -1,
    'out_refund': -1,
}


class account_register_payments(models.TransientModel):
    _inherit = "account.register.payments"
    
    multi = fields.Boolean(string='Multi', help='Technical field indicating if the user selected invoices from multiple partners or from different types.')
    invoice_ids = fields.Many2many('account.invoice', string='Invoices', copy=False)

    @api.multi
    def _groupby_invoices(self):
        '''Split the invoices linked to the wizard according to their commercial partner and their type.

        :return: a dictionary mapping (commercial_partner_id, type) => invoices recordset.
        '''
        results = {}
        # Create a dict dispatching invoices according to their commercial_partner_id and type
        for inv in self.invoice_ids:
            key = (inv.commercial_partner_id.id, MAP_INVOICE_TYPE_PARTNER_TYPE[inv.type])
            if not key in results:
                results[key] = self.env['account.invoice']
            results[key] += inv
        return results
    
    @api.model
    def _compute_payment_amount(self, invoice_ids):
        payment_currency = self.currency_id or self.journal_id.currency_id or self.journal_id.company_id.currency_id

        total = 0
        for inv in invoice_ids:
            if inv.currency_id == payment_currency:
                total += MAP_INVOICE_TYPE_PAYMENT_SIGN[inv.type] * inv.residual_company_signed
            else:
                amount_residual = inv.company_currency_id.with_context(date=self.payment_date).compute(
                    inv.residual_company_signed, payment_currency)
                total += MAP_INVOICE_TYPE_PAYMENT_SIGN[inv.type] * amount_residual
        return total


    @api.multi
    def _prepare_payment_vals(self, invoices):
        '''Create the payment values.

        :param invoices: The invoices that should have the same commercial partner and the same type.
        :return: The payment values as a dictionary.
        '''
        amount = self._compute_payment_amount(invoices) if self.multi else self.amount
        payment_type = ('inbound' if amount > 0 else 'outbound') if self.multi else self.payment_type
        return {
            'journal_id': self.journal_id.id,
            'payment_method_id': self.payment_method_id.id,
            'payment_date': self.payment_date,
            'communication': self.communication,
            'invoice_ids': [(6, 0, invoices.ids)],
            'payment_type': payment_type,
            'amount': abs(amount),
            'currency_id': self.currency_id.id,
            'partner_id': invoices[0].commercial_partner_id.id,
            'partner_type': MAP_INVOICE_TYPE_PARTNER_TYPE[invoices[0].type],
        }



    @api.multi
    def get_payments_vals(self):
        '''Compute the values for payments.

        :return: a list of payment values (dictionary).
        '''
        if self.multi:
            groups = self._groupby_invoices()
            return [self._prepare_payment_vals(invoices) for invoices in groups.values()]
        return [self._prepare_payment_vals(self.invoice_ids)]

    
    @api.multi
    def create_payment_new(self):
#         New V11
        Payment = self.env['account.payment']
        payments = Payment
        for payment_vals in self.get_payments_vals():
            payments += Payment.create(payment_vals)
        return payments.post()
        return {'type': 'ir.actions.act_window_close'}
#         return {
#             'name': _('Payments'),
#             'domain': [('id', 'in', payments.ids), ('state', '=', 'posted')],
#             'view_type': 'form',
#             'view_mode': 'tree,form',
#             'res_model': 'account.payment',
#             'view_id': False,
#             'type': 'ir.actions.act_window',
#         }
# 
# #        old v10
#         payment = self.env['account.payment'].create(self.get_payment_vals())
#         payment.post()
#         return {'type': 'ir.actions.act_window_close'}

    @api.multi
    def create_payment(self):
#         if self.payment_method_code == 'manual' and self.payment_type=='outbound':
#             generate_uob_obj = self.env['generate.uob.files.wiz']
#             res = generate_uob_obj.new().do_generate(self.journal_id)
#             super_res = self.create_payment_new()
#             return res 
#         else:
            return self.create_payment_new()
        

    @api.model
    def default_get(self, fields):
        rec = super(models.TransientModel, self).default_get(fields)
        context = dict(self._context or {})
        active_model = context.get('active_model')
        active_ids = context.get('active_ids')

        # Checks on context parameters
        if not active_model or not active_ids:
            raise UserError(_("Programmation error: wizard action executed without active_model or active_ids in context."))
        if active_model != 'account.invoice':
            raise UserError(_("Programmation error: the expected model for this action is 'account.invoice'. The provided one is '%d'.") % active_model)

        # Checks on received invoice records
        invoices = self.env[active_model].browse(active_ids)
        if any(invoice.state != 'open' for invoice in invoices):
            raise UserError(_("You can only register payments for open invoices"))
        
#         if any(inv.commercial_partner_id != invoices[0].commercial_partner_id for inv in invoices):
#             raise UserError(_("In order to pay multiple invoices at once, they must belong to the same commercial partner."))
        
        if any(MAP_INVOICE_TYPE_PARTNER_TYPE[inv.type] != MAP_INVOICE_TYPE_PARTNER_TYPE[invoices[0].type] for inv in invoices):
            raise UserError(_("You cannot mix customer invoices and vendor bills in a single payment."))
        
        if any(inv.currency_id != invoices[0].currency_id for inv in invoices):
            raise UserError(_("In order to pay multiple invoices at once, they must use the same currency."))
        
        multi = any(inv.commercial_partner_id != invoices[0].commercial_partner_id
            or MAP_INVOICE_TYPE_PARTNER_TYPE[inv.type] != MAP_INVOICE_TYPE_PARTNER_TYPE[invoices[0].type]
            for inv in invoices)

        total_amount = self._compute_payment_amount(invoices)
        communication = ' '.join([ref for ref in invoices.mapped('reference') if ref])

        rec.update({
            'amount': abs(total_amount),
            'currency_id': invoices[0].currency_id.id,
            'payment_type': total_amount > 0 and 'inbound' or 'outbound',
            'partner_id': invoices[0].commercial_partner_id.id,
            'partner_type': MAP_INVOICE_TYPE_PARTNER_TYPE[invoices[0].type],
            'communication': communication,
            'invoice_ids': [(6, 0, invoices.ids)],
            'multi': multi,
        })
        return rec

class GenerateUobFilesWiz(models.TransientModel):
    _name = "generate.uob.files.wiz"

    @api.multi
    def do_generate(self, journal):
        journal_obj = self.env['account.journal']
        inv_obj = self.env['account.invoice']
        bank_file_obj = self.env['bank.file.attachment']
        attachment_obj = self.env['ir.attachment']
        partner_bank_obj = self.env['res.partner.bank']
#         journal_brw = journal_obj.search([('type','=','bank'),('bank_id.bank_uob','=',True)])
#         if not journal_brw:
        if not journal.bank_id or not (journal.bank_id and journal.bank_id.bank_uob):
            raise UserError(_('Please , Configure UOB Account in Journal or select UOB bank Journal.'))
        inv_brw = inv_obj.browse(self._context.get('active_ids',[]))
#         print "journal_brw...",journal_brw
#         print k
#        if inv_brw.filtered(lambda inv: inv.state != 'manual'):
#            raise UserError(_('Invoice must be validated and Should be in Ready to Pay State.'))
        out_txt_filename = tempfile.mktemp("test.TXT")
        fp_pdf = open(out_txt_filename, 'w+')
         
        f_ln = ' '*80
        l1_1 = '1'+'IBGINORM  '
        f_ln = f_ln.replace(f_ln[0:11],l1_1,1)
        code = journal.bank_id.bic
        if not code or len(code) != 7:
            raise UserError(_('Bank Code + Branch code  must have 7 Digit.'))
        f_ln = f_ln[:11] + code + f_ln[18:]
        account_no = journal.bank_acc_number.rjust(11, '0')
        if not account_no or len(account_no) > 11:
            raise UserError(_('Bank Journal must have Account Number with 11 digit.'))
        f_ln = f_ln[:18] + account_no + f_ln[29:]
        acc_name = journal.company_id.name.upper()
        f_ln = f_ln[:29] + acc_name + f_ln[29+len(acc_name):]
        f_ln = f_ln[:49] + time.strftime("%Y%m%d") + f_ln[57:]
        f_ln = f_ln[:57] + time.strftime("%Y%m%d") + f_ln[65:]
        f_ln = f_ln[:70] + '2' + f_ln[71:]
        fp_pdf.write(f_ln+'\r\n')
        credit_total = 0.00
        count_rec = 0
        inv_dict = defaultdict(list)
        for i in inv_brw:
            inv_dict[i.partner_id.id].append(i)  # increment element's value by 1
#         group_invoice_ids = [list(v) for k,v in itertools.groupby(inv_brw.mapped())]
        for list_ndx in inv_dict:
            inv = inv_dict[list_ndx][0]
            s_ln = ' '*80
            s_ln = s_ln[:0] + '2' +s_ln[1:]
            if not inv.partner_id.is_giro_payment:
                raise ValidationError(_('GIRO Payment not activated for %s , You can pay by Cash Or Check')%(inv.partner_id.name))
            bank_ids = partner_bank_obj.search([('partner_id','=',inv.partner_id.id)])
            if not bank_ids:
                raise UserError(_('Please Configure Bank Account for Receiving Person (%s), Or pay by Cash Or Check')%(inv.partner_id.name))
            part_acc_code = bank_ids[0].bank_id.bic 
            if not part_acc_code or len(part_acc_code) > 7:
                raise UserError(_('(%s) Bank Code + Branch code  must have 7 Digit.')%(bank_ids[0].bank_id.name))
        
            s_ln = s_ln[:1] + part_acc_code + s_ln[8:]
            part_acc_number = bank_ids[0].acc_number
            s_ln = s_ln[:8] + part_acc_number + s_ln[8+len(part_acc_number):]
            part_acc_name = inv.partner_id.name.upper()
            s_ln = s_ln[:19] + part_acc_name + s_ln[19+len(part_acc_name):]
            s_ln = s_ln[:39] + '20' + s_ln[41:]
            invoice_amount = 0.0
            for inv_A in inv_dict[list_ndx]:
                invoice_amount += inv_A.amount_total
                
            credit_total += invoice_amount
            amt_blank = '0'*11
#             amt = str(int(invoice_amount*100))
            amt = ('%.2f'%invoice_amount).replace('.','')
            tot_amt = amt_blank[:11-len(amt)] + amt + amt_blank[11:]
            s_ln = s_ln[:41] + tot_amt + s_ln[52:]
            fp_pdf.write(s_ln+'\r\n')
            count_rec += 1
        
        l_ln = ' '*80
        l_ln = l_ln[:0] + '9' +l_ln[1:]
        l_ln = l_ln[:1] + ('0'*13) +l_ln[14:]
        credit_blank = '0'*13
#         credit_total_ch = str(int(credit_total*100))
        credit_total_ch = ('%.2f'%credit_total).replace('.','')
        tot_credit_amt = credit_blank[:13-len(credit_total_ch)] + credit_total_ch + credit_blank[13:]
        l_ln = l_ln[:14] + tot_credit_amt + l_ln[27:]
        l_ln = l_ln[:27] + ('0'*7) + l_ln[34:]
        cnt = str(count_rec)
        l_ln = l_ln[:34] + ('0'*(7-len(cnt)))+cnt + l_ln[41:]
        l_ln = l_ln[:41] + ('0'*13) + l_ln[54:]
        l_ln = l_ln[:54] + '0000054987300' + l_ln[67:]
        fp_pdf.write(l_ln+'\r\n')
        fp_pdf.close()
        file_obj = open(out_txt_filename,'r')
        num_of_file = bank_file_obj.search([('file_date','=',fields.Date.today()),('bank_file_type','=','uob')],count=True)
        num_of_file += 1
        
        Fileno = (num_of_file > 9 and str(num_of_file)) or ('0'+str(num_of_file)) 
        Fname = 'UITI'+time.strftime("%d%m")+ Fileno + '.TXT'
        attachment_id = attachment_obj.create({'name':str(Fname), 'datas':file_obj.read().encode('base64'), 'datas_fname':Fname, 'res_model':'bank.file.attachment','mimetype': 'text/csv','type': 'binary' })
        
        bank_file_id = bank_file_obj.create({'name':attachment_id.name, 'attachment_id':attachment_id.id, 'bank_file_type':'uob', 'invoice_ids':[(6,0,inv_brw.mapped('id'))]})
        ctx = dict(self._context or {})
#        ctx['manual'] = True
#        res = inv_brw.with_context(ctx).write({'state':'paid'})
        return {
                'name': _('Created Bank Files'),
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'tree,form',
                'res_model': 'bank.file.attachment',
                'domain': [
                    ['id', 'in', [x.id for x in bank_file_id]],
                ],
            }
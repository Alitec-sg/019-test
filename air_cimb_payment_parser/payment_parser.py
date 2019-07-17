# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

from odoo.exceptions import UserError, RedirectWarning, ValidationError
import tempfile
import time
import base64
from collections import defaultdict
import re


class ResBank(models.Model):
    _inherit = "res.bank"

    bank_cimb = fields.Boolean('CIMB', default=False)
    org_code = fields.Char('Organization Code', size=5)


class GenerateUobFilesWiz(models.TransientModel):
    _inherit = "generate.uob.files.wiz"

    @api.multi
    def do_generate(self, journal):
        journal_obj = self.env['account.journal']
        inv_obj = self.env['account.invoice']
        bank_file_obj = self.env['bank.file.attachment']
        attachment_obj = self.env['ir.attachment']
        partner_bank_obj = self.env['res.partner.bank']
        if not journal.bank_id or  (not journal.bank_id.bank_uob and not journal.bank_id.bank_cimb):
            raise UserError(_('Please , Configure UOB/CIMB Account in Journal or select Correct bank( UOB/CIMB) Journal.'))
        if journal.bank_id.bank_uob:
            return super(GenerateUobFilesWiz, self).do_generate(journal)
        if not journal.bank_id.org_code or len(journal.bank_id.org_code)!=5:
            raise UserError(_('Please , Set 5 digit Organization Code correctly on Bank.'))
        inv_brw = inv_obj.browse(self._context.get('active_ids',[]))
        out_txt_filename = tempfile.mktemp("test.TXT")
        fp_pdf = open(out_txt_filename, 'w+')
        f_ln = ' '*73
        f_ln = f_ln[:0] + '01' + f_ln[2:]
        f_ln = f_ln[:2] + journal.bank_id.org_code + f_ln[7:]
        f_ln = f_ln[:7] + journal.company_id.name.upper() + f_ln[47:]
        f_ln = f_ln[:47] + time.strftime("%d%m%Y") + f_ln[55:]
        f_ln = f_ln[:55] + ('0'*16) + f_ln[71:]
        f_ln = f_ln[:71] + '  ' + f_ln[73:]
        fp_pdf.write(f_ln+'\r\n')
        
        credit_total = 0.00
        count_rec = 0
        inv_dict = defaultdict(list)
        for i in inv_brw:
            inv_dict[i.partner_id.id].append(i)
        for list_ndx in inv_dict:
            inv = inv_dict[list_ndx][0]    
            s_ln = ' '*127
            s_ln = s_ln[:0] + '02' +s_ln[2:]
            if not inv.partner_id.is_giro_payment:
                raise ValidationError(_('GIRO Payment not activated for %s , You can pay by Cash Or Check')%(inv.partner_id.name))
            bank_ids = partner_bank_obj.search([('partner_id','=',inv.partner_id.id)])
            if not bank_ids:
                raise UserError(_('Please Configure Bank Account for Receiving Person (%s), Or pay by Cash Or Check')%(inv.partner_id.name))
            part_acc_code = bank_ids[0].bank_id.bic 
            if not part_acc_code or len(part_acc_code) != 7:
                raise UserError(_('(%s) BNM code  must have 7 Digit.\n \
                                Ex. CIMB code is 35, you have to enter code 3500000')%(bank_ids[0].bank_id.name))
            s_ln = s_ln[:2] + part_acc_code + s_ln[9:]
            part_acc_number = bank_ids[0].acc_number
            s_ln = s_ln[:9] + part_acc_number + s_ln[9+len(part_acc_number):]
            part_acc_name = inv.partner_id.name.upper()
            s_ln = s_ln[:25] + part_acc_name  + s_ln[25+len(part_acc_name):]
            invoice_amount = 0.0
            for inv_A in inv_dict[list_ndx]:
                invoice_amount += inv_A.amount_total
                
            credit_total += invoice_amount
            amt_blank = '0'*11
#             amt = str(int(invoice_amount*100))
#             amt = repr(invoice_amount).replace('.','')
            amt = ('%.2f'%invoice_amount).replace('.','')
            tot_amt = amt_blank[:11-len(amt)] + amt + amt_blank[11:]
            s_ln = s_ln[:65] + tot_amt + s_ln[76:]
            ref = re.sub('[/-]', '', (inv.partner_id.ref or ''))
            s_ln = s_ln[:76] + ref + s_ln[76+len(ref):]
            s_ln = s_ln[:106]+ ref + s_ln[106+len(ref):]
            s_ln = s_ln[:126] + '2'
            fp_pdf.write(s_ln+'\r\n')
            count_rec += 1
            
        l_ln = ' '*21
        l_ln = l_ln[:0] + '03' +l_ln[2:]
        cnt = str(count_rec)
        l_ln = l_ln[:2] + ('0'*(6-len(cnt)))+cnt + l_ln[8:]
        
        credit_blank = '0'*13
#         credit_total_ch = str(int(credit_total*100))
#         credit_total_ch = repr(credit_total).replace('.','')
        credit_total_ch = ('%.2f'%credit_total).replace('.','')
        tot_credit_amt = credit_blank[:13-len(credit_total_ch)] + credit_total_ch + credit_blank[13:]
        l_ln = l_ln[:8] + tot_credit_amt + l_ln[21:]
        fp_pdf.write(l_ln+'\r\n')
        
        
        
        fp_pdf.close()
        file_obj = open(out_txt_filename,'r')
        num_of_file = bank_file_obj.search([('file_date','=',fields.Date.today()),('bank_file_type','=','cimb')],count=True)
        num_of_file += 1
        
        Fileno = (num_of_file > 9 and str(num_of_file)) or ('0'+str(num_of_file)) 
        Fname = 'CIMB'+time.strftime("%d%m")+ Fileno + '.TXT'
        attachment_id = attachment_obj.create({'name':str(Fname), 'datas':file_obj.read().encode('base64'), 'datas_fname':Fname, 'res_model':'bank.file.attachment','mimetype': 'text/csv','type': 'binary' })
        
        bank_file_id = bank_file_obj.create({'name':attachment_id.name, 'attachment_id':attachment_id.id,'bank_file_type':'cimb',  'invoice_ids':[(6,0,inv_brw.mapped('id'))]})
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
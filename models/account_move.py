# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime
 
class AccountMove(models.Model):
    _inherit ='account.move'
 
   
    @api.constrains('invoice_line_ids', 'operation_unit_id')
    def _check_single_ou(self):
        for move in self:
            ous = self.env['operation.unit']

            # 1️⃣ OU من الفاتورة نفسها
            if move.operation_unit_id:
                ous |= move.operation_unit_id

            # 2️⃣ OU من سطور الفاتورة
            for line in move.invoice_line_ids:
                if line.operation_unit_id:
                    ous |= line.operation_unit_id

                # من sale order
                if line.sale_line_ids:
                    ous |= line.sale_line_ids.mapped(
                        'order_id.operation_unit_id'
                    )

                # من purchase order
                if line.purchase_line_id:
                    ous |= line.purchase_line_id.order_id.operation_unit_id

            ous = ous.filtered(lambda x: x)

            if len(ous) > 1:
                raise ValidationError(
                    _('You cannot mix multiple Operation Units in one invoice. move[%s] in move line [%s] in sale [%s] in purchase [%s]' %())
                )
     
    def _compute_from_other_order(self):
        for move in self:
            is_exsiting_sale_field = self.env['ir.model.fields'].sudo().search(
                [('name', '=', 'sale_line_ids'), ('model', '=', 'account.move.line')])
            is_exsiting_purchase_field = self.env['ir.model.fields'].sudo().search(
                [('name', '=', 'purchase_line_id'), ('model', '=', 'account.move.line')])
            is_exsiting_stock_field = self.env['ir.model.fields'].sudo().search(
                [('name', '=', 'stock_valuation_layer_ids'), ('model', '=', 'account.move.line')])
            from_sale_order=False
            from_purch_order=False
            from_stock_order=False
            if is_exsiting_sale_field:
                from_sale_order = bool(move.invoice_line_ids.mapped('sale_line_ids.order_id'))
              
            if is_exsiting_purchase_field:
                from_purch_order = bool(move.invoice_line_ids.mapped('purchase_line_id.order_id'))
             
            if is_exsiting_stock_field:
                from_stock_order = bool(move.stock_valuation_layer_ids)
              
          
            if from_sale_order or from_purch_order or from_stock_order:
                move.from_other_order = True
        
            else:
                move.from_other_order =  False

            return super()._compute_from_other_order()
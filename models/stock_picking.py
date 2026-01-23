# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    operation_unit_id = fields.Many2one(
        'operation.unit',
        readonly=True,
       
        copy=False
    )
    def _is_return_picking(self):
        self.ensure_one()
        return any(
            self.move_ids_without_package.mapped('origin_returned_move_id')
        )


    # from_other_order = fields.Boolean(
    #     string='From Other Document',
    #     compute='_compute_from_other_document',
     
    # )

    # @api.depends('sale_id', 'purchase_id', 'move_ids_without_package')
    # def _compute_from_other_document(self):
    #     for picking in self:
    #         picking.from_other_order = bool(
    #             picking.sale_id
    #             or picking.purchase_id
    #             or  picking._is_return_picking()

    #         )
 
    # allowed_ou_domain = fields.Char(compute="get_allowed_ou_domain")

    # @api.depends('company_id','invoice_user_id')
    # def get_allowed_ou_domain(self):
    #     for rec in self:
    #         rec.allowed_ou_domain = [('id','in',self.env.user.ou_config_ids.filtered(lambda x: x.company_id.id == rec.company_id.id).allowed_ou_ids.ids)]

    # @api.model
    # def default_get(self, fields_list):
    #     res = super().default_get(fields_list)

    #     company_id = res.get('company_id', self.env.company.id)

    #     if not res.get('operation_unit_id'):
    #         ou = self.env.user.ou_config_ids.filtered(
    #             lambda x: x.company_id.id == company_id
    #         ).default_ou_id

    #         if ou:
    #             res['operation_unit_id'] = ou.id

    #     return res
    
    # @api.onchange('company_id')
    # def _onchange_company_id_set_ou(self):
    #     for rec in self:
    #         if not rec.company_id:
    #             rec.operation_unit_id = False
    #             return

    #         # OU الحالي غير تابع للشركة
    #         if rec.operation_unit_id and rec.operation_unit_id.company_id != rec.company_id:
    #             rec.operation_unit_id = False

    #         # تعيين OU افتراضي
    #         if not rec.operation_unit_id:
    #             ou = self.env.user.ou_config_ids.filtered(
    #                 lambda x: x.company_id == rec.company_id
    #             ).default_ou_id

    #             if ou:
    #                 rec.operation_unit_id = ou

    # allow_modify_ou_flag = fields.Boolean(
    #     default=lambda self: self._default_allow_modify_ou_flag(),
    #     compute="_check_allow_modify_ou_flag",
    # )

    # def _default_allow_modify_ou_flag(self):
        
    #     return self.user_has_groups('yousentech_invoicing_ou.group_allow_modify_ou')

    # def _check_allow_modify_ou_flag(self):
        
    #     for rec in self:
    #         rec.allow_modify_ou_flag = self.user_has_groups('yousentech_invoicing_ou.group_allow_modify_ou')

    @api.model
    def create(self, vals):
        picking = super().create(vals)
        if not picking.operation_unit_id:
            picking.operation_unit_id = self.env.user.ou_config_ids.filtered(lambda x: x.company_id.id == picking.company_id.id).default_ou_id.id
        
        # لو كان مرتجع
        if picking._is_return_picking():
            original_pickings = picking.move_ids_without_package.mapped(
                'origin_returned_move_id.picking_id'
            )
            if original_pickings:
                picking.operation_unit_id = original_pickings[0].operation_unit_id.id

        return picking


    def button_validate(self):
        for picking in self:
            if not picking.operation_unit_id:
                raise ValidationError(
                    'Operation Unit is required before validating the picking.'
                )

            ou = picking.operation_unit_id
            user = self.env.user

            if not ou:
                raise ValidationError("Operation Unit is required on this document.")

            if ou.company_id != picking.company_id:
                raise ValidationError(
                    "The selected Operation Unit does not belong to the same company as this document."
                )

            if user.ou_config_ids.filtered(lambda x: x.company_id.id == picking.company_id.id).allowed_ou_ids and ou not in user.ou_config_ids.filtered(lambda x: x.company_id.id == picking.company_id.id).allowed_ou_ids:
                raise ValidationError(
                    "The selected Operation Unit is not allowed for the current user."
                )
           
            picking._assign_ou_to_moves()

        return super().button_validate()


    def _assign_ou_to_moves(self):
        for picking in self:
            if picking.operation_unit_id:
                for line in picking.move_ids_without_package:
                    line.write({
                            'operation_unit_id': picking.operation_unit_id.id
                        })

    # @api.onchange('operation_unit_id')
    # def _onchange_operation_unit_id_sync_returns(self):
    #     for picking in self:
    #         if not picking.operation_unit_id:
    #             continue

    #         # لا تطبق على المرتجع نفسه
    #         if picking._is_return_picking():
    #             continue

    #         # المرتجعات التابعة
    #         return_pickings = self.env['stock.picking'].search([
    #             ('move_ids_without_package.origin_returned_move_id.picking_id', '=', picking.id),
    #         ])

    #         for return_picking in return_pickings:
    #             return_picking.operation_unit_id = picking.operation_unit_id
    #             for layer in  return_picking.move_ids_without_package.stock_valuation_layer_ids:
    #                 layer.account_move_id.write({'operation_unit_id': picking.operation_unit_id.id})

class StockMove(models.Model):
    _inherit = 'stock.move' 

    operation_unit_id = fields.Many2one(
        'operation.unit',
        readonly=True,
       
        copy=False
    )


    def _get_new_picking_values(self):
        vals = super()._get_new_picking_values()

        # 🔹 إذا الشحنة الجديدة ناتجة عن شحنة سابقة
        if self.picking_id and self.picking_id.operation_unit_id:
            vals['operation_unit_id'] = self.picking_id.operation_unit_id.id
            return vals

        # من أمر البيع
        if self.sale_line_id and self.sale_line_id.order_id.operation_unit_id:
            vals['operation_unit_id'] = self.sale_line_id.order_id.operation_unit_id.id
            _logger.warning(
                "OU FROM SALE ORDER %s → %s",
                self.sale_line_id.order_id.name,
                vals['operation_unit_id']
            )
            return vals

        # من أمر الشراء
        if self.purchase_line_id and self.purchase_line_id.order_id.operation_unit_id:
            vals['operation_unit_id'] = self.purchase_line_id.order_id.operation_unit_id.id
            _logger.warning(
                "OU FROM PURCHASE ORDER %s → %s",
                self.purchase_line_id.order_id.name,
                vals['operation_unit_id']
            )
            return vals

        # fallback
        vals['operation_unit_id'] =  self.env.user.ou_config_ids.filtered(lambda x: x.company_id.id == self.company_id.id).default_ou_id.id
        _logger.warning(
            "OU FROM USER DEFAULT → %s",
            vals['operation_unit_id']
        )
        return vals
 
 
    def _prepare_account_move_vals(self):
        vals = super()._prepare_account_move_vals()

        ou = False
 
        if self.stock_valuation_layer_ids:
            ou = self.stock_valuation_layer_ids[0].operation_unit_id
 
        if not ou and self.picking_id and self.picking_id.operation_unit_id:
            ou = self.picking_id.operation_unit_id
 
        if not ou:
            ou =  self.env.user.ou_config_ids.filtered(lambda x: x.company_id.id == self.company_id.id).default_ou_id
 
        if ou:
            vals['operation_unit_id'] = ou.id

        return vals
        
    def _prepare_account_move_vals(self, acc_valuation,  acc_dest,  journal_id, qty,  description, svl_id,cost ):
        vals = super()._prepare_account_move_vals(
            acc_valuation,
            acc_dest,
            journal_id,
            qty,
            description,
            svl_id,
            cost
        )

        ou = False

        # 1️⃣ من valuation layer
        if self.stock_valuation_layer_ids:
            ou = self.stock_valuation_layer_ids[0].operation_unit_id

        # 2️⃣ من picking
        if not ou and self.picking_id and self.picking_id.operation_unit_id:
            ou = self.picking_id.operation_unit_id

        # 3️⃣ fallback
        if not ou:
            ou =  self.env.user.ou_config_ids.filtered(lambda x: x.company_id.id == self.company_id.id).default_ou_id

        if ou:
            vals['operation_unit_id'] = ou.id

        return vals

   
    def _prepare_account_move_line( self, qty, cost, credit_account_id, debit_account_id,  svl_id, description):
        lines = super()._prepare_account_move_line(
            qty,
            cost,
            credit_account_id,
            debit_account_id,
            svl_id,
            description
        )

        ou = (
            self.stock_valuation_layer_ids[:1].operation_unit_id
            or self.picking_id.operation_unit_id
            or  self.env.user.ou_config_ids.filtered(lambda x: x.company_id.id == self.company_id.id).default_ou_id
        )

        if ou:
            for line in lines:
                line[2]['operation_unit_id'] = ou.id

        return lines

        



class StockValuationLayer(models.Model):
    _inherit = 'stock.valuation.layer'

    operation_unit_id = fields.Many2one(
        'operation.unit',
        string='Operation Unit',
        readonly=True,
        related='stock_move_id.operation_unit_id',
        store=True,
        copy=False
    )



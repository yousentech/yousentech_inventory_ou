# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

class saleOrder(models.Model):
    _inherit = 'sale.order' 


   def write(self, vals):
        res = super().write(vals)

        if 'operation_unit_id' in vals:
            for order in self:
                pickings = order.picking_ids 
                pickings.write({
                    'operation_unit_id': order.operation_unit_id.id
                })

                # Stock Moves
                pickings.move_ids_without_package.write({
                    'operation_unit_id': order.operation_unit_id.id
                })
                for layer in  pickings.move_ids_without_package.stock_valuation_layer_ids
                layer.account_move_id.write({'operation_unit_id': order.operation_unit_id.id})

        return res

# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 Zaber Technologies Inc. (<http://zaber.com>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from osv import fields,osv,orm

# Link Account Moves and Stock Moves: http://bugs.izaber.com/issues/1157
class account_move_line(osv.osv):
    _inherit = "account.move.line"
    _columns = {
        'stock_move_ids': fields.many2many(
                              'stock.move', 
                              'stock_account_rel', 
                              'account_move_line_id', 
                              'stock_move_id', 
                              'Stock Moves' ),
    }




# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class PizzaProductionOrder(models.Model):
    _name = 'pizza.production.order'
    _description = '3.4.3.3 - Lệnh Sản Xuất Pizza'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # --- 1. CÁC HÀM MẶC ĐỊNH TÌM KHO ---
    def _get_default_internal_location(self):
        return self.env['stock.location'].search([('usage', '=', 'internal')], limit=1, order='id').id

    def _get_default_production_location(self):
        return self.env['stock.location'].search([('usage', '=', 'production')], limit=1, order='id').id

    # --- HEADER ---
    name = fields.Char('Mã lệnh', default='Mới', readonly=True)
    origin = fields.Char('Nguồn gốc', help="Lệnh này sinh ra từ đơn hàng nào (VD: SO001)", readonly=True)
    
    pizza_id = fields.Many2one(
        'product.product', 'Loại Pizza', 
        domain="[('type', '=', 'product')]", required=True
    )
    
    qty_producing = fields.Float('Số lượng làm', default=1.0, required=True)

    uom_id = fields.Many2one(
        'uom.uom', 'Đơn vị', 
        related='pizza_id.uom_id', 
        readonly=True, store=True
    )
    
    bom_id = fields.Many2one(
        'mrp.bom', 'Công thức (BOM)',
        help="Công thức để sản xuất loại Pizza này"
    )

    date_planned = fields.Datetime('Ngày kế hoạch', default=fields.Datetime.now)
    user_id = fields.Many2one('res.users', 'Bếp trưởng', default=lambda self: self.env.user)

    # --- CHI TIẾT NGUYÊN LIỆU ---
    move_raw_ids = fields.One2many('pizza.production.line', 'production_id', string='Nguyên liệu tiêu hao')

    # --- TRẠNG THÁI ---
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('confirmed', 'Đã xác nhận (Đủ hàng)'),
        ('progress', 'Đang chế biến (Nướng)'),
        ('qc_check', 'Kiểm tra chất lượng (QC)'),
        ('done', 'Hoàn thành'),
        ('cancel', 'Hủy'),
    ], default='draft', string='Tiến độ', tracking=True)

    # --- CẤU HÌNH KHO ---
    location_src_id = fields.Many2one(
        'stock.location', 'Kho Nguyên liệu (Nguồn)', required=True,
        default=_get_default_internal_location
    )
    
    location_dest_id = fields.Many2one(
        'stock.location', 'Kho Thành phẩm (Đích)', required=True,
        default=_get_default_internal_location
    )
    
    production_location_id = fields.Many2one(
        'stock.location', 'Kho Ảo Sản xuất', required=True,
        default=_get_default_production_location
    )

    # --- LOGIC KHỞI TẠO ---
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Mới') == 'Mới':
                vals['name'] = self.env['ir.sequence'].next_by_code('pizza.production.order') or 'Mới'
        return super(PizzaProductionOrder, self).create(vals_list)

    @api.onchange('pizza_id', 'qty_producing')
    def _onchange_pizza_details(self):
        if not self.pizza_id:
            return
        
        bom = self.env['mrp.bom'].search([
            ('product_tmpl_id', '=', self.pizza_id.product_tmpl_id.id)
        ], limit=1)

        if bom:
            self.bom_id = bom.id
            self._update_lines_from_bom()
        else:
            self.move_raw_ids = [(5, 0, 0)]
            self.bom_id = False
            return {
                'warning': {
                    'title': _("Chưa có công thức"),
                    'message': _("Sản phẩm '%s' chưa có Công thức (BOM). Vui lòng cấu hình trước!") % self.pizza_id.name
                }
            }
    
    @api.onchange('bom_id')
    def _onchange_bom_id(self):
        self._update_lines_from_bom()

    def _update_lines_from_bom(self):
        if not self.bom_id:
            return
        lines = []
        for bom_line in self.bom_id.bom_line_ids:
            total_qty = bom_line.product_qty * self.qty_producing
            lines.append((0, 0, {
                'product_id': bom_line.product_id.id,
                'qty_needed': total_qty,
                'uom_id': bom_line.product_uom_id.id,
            }))
        self.move_raw_ids = [(5, 0, 0)] + lines

    # =========================================================
    # HÀM KIỂM TRA KHO (ĐỦ HÀNG & HẠN DÙNG)
    # =========================================================
    def action_check_stock(self):
        if not self.bom_id:
            raise UserError(_("Bạn chưa chọn Công thức (BOM)!"))

        if not self.move_raw_ids:
            raise UserError(_("Công thức này không có nguyên liệu nào."))

        missing_items = []
        expired_items = []

        for line in self.move_raw_ids:
            # 1. Kiểm tra SỐ LƯỢNG
            if line.qty_available < line.qty_needed:
                missing_items.append(f"{line.product_id.name} (Thiếu {line.qty_needed - line.qty_available})")
            
            # 2. Kiểm tra HẠN SỬ DỤNG
            tmpl = line.product_id.product_tmpl_id
            if tmpl.expired_lot_count > 0:
                expired_items.append(line.product_id.name)

        if expired_items:
            msg = "⛔ DỪNG SẢN XUẤT! Các nguyên liệu sau ĐÃ HẾT HẠN/HỎNG: " + ", ".join(expired_items)
            return {
                'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': 'Cảnh báo An toàn!', 'message': msg, 'type': 'danger', 'sticky': True}
            }

        if missing_items:
            msg = "Thiếu nguyên liệu: " + ", ".join(missing_items)
            return {
                'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': 'Không đủ hàng!', 'message': msg, 'type': 'warning', 'sticky': False}
            }

        self.state = 'progress' 
        self.message_post(body="✅ Đã kiểm tra: Đủ nguyên liệu & Hạn dùng tốt. Bắt đầu chế biến.")
        return {
            'effect': {'fadeout': 'fast', 'message': 'Nguyên liệu TƯƠI NGON! Bắt đầu nấu...', 'type': 'rainbow_man'}
        }

    # =========================================================
    # LOGIC HOÀN THÀNH (FIXED ODOO 18)
    # =========================================================
    def action_done(self):
        if self.state == 'done':
            raise UserError(_("Lệnh này đã hoàn thành rồi!"))
        
        if self.state == 'cancel':
            raise UserError(_("Đơn hàng này đã bị Hủy, không thể nhập kho!"))


        # Sử dụng try/except: Nếu Odoo chặn (do đã có lịch sử), ta BỎ QUA và vẫn cho nhập kho
        try:
            product_tmpl = self.pizza_id.product_tmpl_id
            if product_tmpl.type != 'product':
                product_tmpl.sudo().write({'type': 'product'})
        except Exception:
            pass 

        # Tiếp tục quy trình nhập kho
        self._consume_materials()
        self._produce_finished_goods()
        
        self.state = 'done'
        
        return {
            'effect': {
                'fadeout': 'slow',
                'message': _('Đã hoàn thành! (Nếu tồn kho không tăng, hãy kiểm tra lại loại sản phẩm)'),
                'type': 'rainbow_man',
            }
        }
    def _consume_materials(self):
        StockMove = self.env['stock.move']
        StockMoveLine = self.env['stock.move.line']
        
        for line in self.move_raw_ids:
            move = StockMove.create({
                'name': f'Tiêu hao cho {self.name}',
                'product_id': line.product_id.id,
                'product_uom_qty': line.qty_needed,
                'product_uom': line.uom_id.id,
                'location_id': self.location_src_id.id,
                'location_dest_id': self.production_location_id.id,
                'origin': self.name,
                'state': 'draft',
            })
            move._action_confirm()
            move._action_assign()
            
            has_line = False
            if move.move_line_ids:
                for move_line in move.move_line_ids:
                    move_line.quantity = line.qty_needed
                    has_line = True
            
            if not has_line:
                StockMoveLine.create({
                    'move_id': move.id,
                    'product_id': move.product_id.id,
                    'quantity': line.qty_needed,
                    'location_id': move.location_id.id,
                    'location_dest_id': move.location_dest_id.id,
                })
            
            move.picked = True 
            move._action_done()

    def _produce_finished_goods(self):
        StockMove = self.env['stock.move']
        StockMoveLine = self.env['stock.move.line']
        
        move = StockMove.create({
            'name': f'Sản xuất xong {self.name}',
            'product_id': self.pizza_id.id,
            'product_uom_qty': self.qty_producing,
            'product_uom': self.pizza_id.uom_id.id,
            'location_id': self.production_location_id.id,
            'location_dest_id': self.location_dest_id.id,
            'origin': self.name,
            'state': 'draft',
        })
        move._action_confirm()
        
        has_line = False
        if move.move_line_ids:
            for move_line in move.move_line_ids:
                move_line.quantity = self.qty_producing
                has_line = True
        
        if not has_line:
            StockMoveLine.create({
                'move_id': move.id,
                'product_id': move.product_id.id,
                'quantity': self.qty_producing,
                'location_id': move.location_id.id,
                'location_dest_id': move.location_dest_id.id,
            })
            
        move.picked = True
        move._action_done()

    # --- ACTIONS KHÁC ---
    def action_start_cooking(self):
        self.state = 'progress'

    def action_qc_check(self):
        self.state = 'qc_check'

    def action_create_procurement(self):
        self.ensure_one()
        lines_to_buy = []
        for line in self.move_raw_ids:
            if line.qty_available < line.qty_needed:
                missing_qty = line.qty_needed - line.qty_available
                lines_to_buy.append((0, 0, {
                    'product_id': line.product_id.id,
                    'qty': missing_qty,
                    'uom_id': line.uom_id.id,
                }))

        if not lines_to_buy:
            raise UserError(_("Kho nguyên liệu vẫn đủ để sản xuất lệnh này, không cần tạo yêu cầu mua!"))

        warehouse = self.env['stock.warehouse'].search([
            ('lot_stock_id', '=', self.location_src_id.id)
        ], limit=1)
        
        if not warehouse:
            warehouse = self.env['stock.warehouse'].search([], limit=1)

        return {
            'name': _('Tạo Yêu cầu Mua nguyên liệu'),
            'type': 'ir.actions.act_window',
            'res_model': 'pizza.procurement.request',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_warehouse_id': warehouse.id,
                'default_note': _("Tự động tạo bổ sung cho Lệnh SX: %s") % self.name,
                'default_line_ids': lines_to_buy,
            }
        }

    def action_scrap(self):
        return {
            'name': _('Ghi nhận Pizza Hỏng/Cháy'),
            'type': 'ir.actions.act_window',
            'res_model': 'pizza.scrap.record',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_production_id': self.id,
                'default_product_id': self.pizza_id.id,
                'default_qty': 1.0,
            }
        }

class PizzaProductionLine(models.Model):
    _name = 'pizza.production.line'
    _description = 'Chi tiết nguyên liệu tiêu hao'

    production_id = fields.Many2one('pizza.production.order')
    product_id = fields.Many2one('product.product', 'Nguyên liệu', required=True)
    qty_needed = fields.Float('Định mức cần')
    uom_id = fields.Many2one('uom.uom', 'Đơn vị')
    
    qty_available = fields.Float('Tồn kho thực tế', related='product_id.qty_available')
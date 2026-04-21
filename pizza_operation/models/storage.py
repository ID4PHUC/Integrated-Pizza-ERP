# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import timedelta

# ---------------------------------------------------------
# CLASS 1: QUẢN LÝ SẢN PHẨM & TÍNH TOÁN TRẠNG THÁI KHO
# ---------------------------------------------------------
class PizzaProductStorage(models.Model):
    _inherit = 'product.template'

    # --- 1. CÁC TRƯỜNG CẤU HÌNH & THÔNG TIN ---
    storage_category = fields.Selection([
        ('raw', 'Nguyên liệu thô (Bột, Sốt...)'),
        ('cold', 'Kho lạnh (Thịt, Hải sản...)'),
        ('finished', 'Thành phẩm Pizza'),
        ('packing', 'Khu vực đóng gói'),
    ], string='Khu vực lưu trữ')

    last_receipt_date = fields.Datetime(
        string='Ngày nhập gần nhất', 
        compute='_compute_last_receipt_date'
    )

    inspection_date = fields.Datetime(string='Ngày kiểm tra (Hết hạn)')

    expected_expiry_date = fields.Datetime(
        string='Hạn dùng dự kiến (Gợi ý)',
        compute='_compute_expected_expiry',
    )

    # --- 2. CẤU HÌNH FEFO & CẢNH BÁO ---
    check_expiry = fields.Boolean('Kích hoạt cảnh báo hạn dùng', default=False)
    shelf_life = fields.Integer(string='Tuổi thọ (Ngày)', default=0)
    alert_days = fields.Integer('Báo trước (ngày)', default=15)

    # --- 3. CÁC TRƯỜNG HỖ TRỢ GIAO DIỆN ---
    is_inspection_warning = fields.Boolean(
        string='Cảnh báo kiểm tra',
        compute='_compute_inspection_warning'
    )

    # --- 4. BIẾN ĐẾM TRẠNG THÁI ---
    expired_lot_count = fields.Integer(
        string='Trạng thái Hết hạn', 
        compute='_compute_lot_status',
        search='_search_expired_lot_count' 
    )

    expiring_lot_count = fields.Integer(
        string='Trạng thái Sắp hỏng', 
        compute='_compute_lot_status',
        search='_search_expiring_lot_count'
    )

    # =========================================================
    # CÁC HÀM TÍNH TOÁN (COMPUTE)
    # =========================================================
    def _compute_last_receipt_date(self):
        for record in self:
            last_move = self.env['stock.move'].search([
                ('product_id.product_tmpl_id', '=', record.id),
                ('state', '=', 'done'),
                ('picking_type_id.code', '=', 'incoming')
            ], order='date desc', limit=1)
            record.last_receipt_date = last_move.date if last_move else False

    @api.depends('last_receipt_date', 'shelf_life')
    def _compute_expected_expiry(self):
        for record in self:
            if record.last_receipt_date and record.shelf_life > 0:
                record.expected_expiry_date = record.last_receipt_date + timedelta(days=record.shelf_life)
            else:
                record.expected_expiry_date = False

    @api.depends('inspection_date', 'alert_days')
    def _compute_inspection_warning(self):
        now = fields.Datetime.now()
        for record in self:
            record.is_inspection_warning = False
            if record.inspection_date and record.alert_days > 0:
                warning_limit = now + timedelta(days=record.alert_days)
                if now <= record.inspection_date < warning_limit:
                    record.is_inspection_warning = True

    @api.depends('check_expiry', 'alert_days', 'shelf_life', 'inspection_date') 
    def _compute_lot_status(self):
        StockLot = self.env['stock.lot']
        now = fields.Datetime.now()

        for record in self:
            lots_expired = 0
            lots_expiring = 0
            
            if record.check_expiry:
                alert_date = now + timedelta(days=record.alert_days)
                lots_expired = StockLot.search_count([
                    ('product_id.product_tmpl_id', '=', record.id),
                    ('expiration_date', '<', now), 
                    ('quant_ids.quantity', '>', 0),
                    ('quant_ids.location_id.usage', '=', 'internal')
                ])
                lots_expiring = StockLot.search_count([
                    ('product_id.product_tmpl_id', '=', record.id),
                    ('expiration_date', '>=', now),
                    ('expiration_date', '<', alert_date),
                    ('quant_ids.quantity', '>', 0),
                    ('quant_ids.location_id.usage', '=', 'internal')
                ])

            manual_expired = 0
            manual_expiring = 0

            if record.inspection_date:
                if record.inspection_date < now:
                    manual_expired = 1
                elif record.is_inspection_warning:
                    manual_expiring = 1

            record.expired_lot_count = lots_expired + manual_expired
            record.expiring_lot_count = lots_expiring + manual_expiring

    # =========================================================
    # CÁC HÀM TÌM KIẾM (SEARCH)
    # =========================================================
    def _search_expired_lot_count(self, operator, value):
        if operator in ('>', '>=') and value >= 0:
            now = fields.Datetime.now()
            quants = self.env['stock.quant'].search([
                ('lot_id.expiration_date', '<', now),
                ('quantity', '>', 0),
                ('location_id.usage', '=', 'internal')
            ])
            ids_from_lots = quants.mapped('product_id.product_tmpl_id').ids
            products_manual = self.search([
                ('inspection_date', '<', now),
                ('qty_available', '>', 0)
            ])
            ids_from_manual = products_manual.ids
            final_ids = list(set(ids_from_lots + ids_from_manual))
            return [('id', 'in', final_ids)] if final_ids else [('id', '=', -1)]
        return []

    def _search_expiring_lot_count(self, operator, value):
        if operator in ('>', '>=') and value >= 0:
            now = fields.Datetime.now()
            limit_date = now + timedelta(days=30)
            quants = self.env['stock.quant'].search([
                ('lot_id.expiration_date', '>=', now),
                ('lot_id.expiration_date', '<', limit_date),
                ('quantity', '>', 0),
                ('location_id.usage', '=', 'internal')
            ])
            ids_from_lots = quants.mapped('product_id.product_tmpl_id').ids
            products_manual = self.search([
                ('inspection_date', '>=', now),
                ('inspection_date', '<', limit_date),
                ('qty_available', '>', 0)
            ])
            ids_from_manual = products_manual.ids
            final_ids = list(set(ids_from_lots + ids_from_manual))
            return [('id', 'in', final_ids)] if final_ids else [('id', '=', -1)]
        return []
    
    # =========================================================
    # ACTIONS CŨ
    # =========================================================
    def action_check_expiry(self):
        self.ensure_one()
        limit_date = fields.Datetime.now() + timedelta(days=30)
        return {
            'name': _('Kiểm tra Lô Hạn dùng (FEFO)'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.lot',
            'view_mode': 'list,form',
            'domain': [
                ('product_id.product_tmpl_id', '=', self.id),
                ('expiration_date', '<', limit_date),
                ('quant_ids.quantity', '>', 0)
            ],
            'context': {'create': False},
        }

    def action_return_to_vendor(self):
        self.ensure_one()
        vendor_id = self.seller_ids[0].partner_id.id if self.seller_ids else False
        picking_type = self.env['stock.picking.type'].search([('code', '=', 'outgoing')], limit=1)
        return {
            'name': _('Trả hàng cho NCC'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_partner_id': vendor_id,
                'default_picking_type_id': picking_type.id,
                'default_origin': _("Trả hàng: %s") % self.name,
            }
        }

    # =========================================================
    # [FIXED] NÚT HỦY DIỆT SẢN PHẨM (XÓA SẠCH DỮ LIỆU LIÊN QUAN)
    def action_destroy_product(self):
        """Xóa sản phẩm bằng lệnh SQL trực tiếp để bỏ qua ràng buộc"""
        for record in self:
            # 1. Tìm tất cả biến thể (product.product) của sản phẩm này
            product_ids = self.env['product.product'].search([('product_tmpl_id', '=', record.id)]).ids
            
            if product_ids:
                # Tạo tuple ID để dùng trong câu lệnh SQL IN (...)
                ids = tuple(product_ids + [0]) 
                
                # --- XÓA DỮ LIỆU LIÊN QUAN ĐẾN BIẾN THỂ (PRODUCT.PRODUCT) ---
                self.env.cr.execute("DELETE FROM stock_quant WHERE product_id IN %s", (ids,))
                self.env.cr.execute("DELETE FROM stock_move_line WHERE product_id IN %s", (ids,))
                self.env.cr.execute("DELETE FROM stock_move WHERE product_id IN %s", (ids,))
                
                # Xóa dòng nguyên liệu trong BOM khác
                self.env.cr.execute("DELETE FROM mrp_bom_line WHERE product_id IN %s", (ids,))
                
                # Xóa trong các bảng module Pizza
                self.env.cr.execute("DELETE FROM pizza_sales_line WHERE product_id IN %s", (ids,))
                self.env.cr.execute("DELETE FROM pizza_production_line WHERE product_id IN %s", (ids,))
                self.env.cr.execute("DELETE FROM pizza_procurement_line WHERE product_id IN %s", (ids,))
                self.env.cr.execute("DELETE FROM pizza_scrap_record WHERE product_id IN %s", (ids,))
                
                # Xóa Production Order (Lệnh sản xuất) liên quan đến sản phẩm này
                self.env.cr.execute("DELETE FROM pizza_production_order WHERE pizza_id IN %s", (ids,))

            # --- [MỚI] XÓA CÔNG THỨC (BOM) GẮN VỚI SẢN PHẨM NÀY ---
            # Bước 1: Xóa các dòng chi tiết của BOM này trước
            self.env.cr.execute("DELETE FROM mrp_bom_line WHERE bom_id IN (SELECT id FROM mrp_bom WHERE product_tmpl_id = %s)", (record.id,))
            # Bước 2: Xóa chính cái BOM đó
            self.env.cr.execute("DELETE FROM mrp_bom WHERE product_tmpl_id = %s", (record.id,))

            # --- XÓA CHÍNH SẢN PHẨM (TEMPLATE) ---
            self.env.cr.execute("DELETE FROM product_template WHERE id = %s", (record.id,))
            
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'THÀNH CÔNG',
                'message': 'Đã "Hủy diệt" sản phẩm và toàn bộ dữ liệu (Kho, BOM, Đơn hàng...)',
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'}
            }
        }
    
# ---------------------------------------------------------
# CLASS 2: TỰ ĐỘNG ĐIỀN NGÀY HẾT HẠN KHI TẠO LÔ MỚI
# ---------------------------------------------------------
class StockLotAutoExpiry(models.Model):
    _inherit = 'stock.lot'
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('expiration_date') and vals.get('product_id'):
                product = self.env['product.product'].browse(vals.get('product_id'))
                if product.shelf_life > 0:
                    vals['expiration_date'] = fields.Datetime.now() + timedelta(days=product.shelf_life)
        return super(StockLotAutoExpiry, self).create(vals_list)
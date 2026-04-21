from odoo import models, fields, _
from odoo.exceptions import UserError

class PizzaScrap(models.Model):
    _name = 'pizza.scrap.record'
    _description = 'Ghi nhận Hủy/Trả hàng'

    # --- Header ---
    production_id = fields.Many2one('pizza.production.order', 'Lệnh SX', readonly=True)
    product_id = fields.Many2one('product.product', 'Sản phẩm lỗi', required=True)
    qty = fields.Float('Số lượng hủy', default=1.0, required=True)
    
    # Thêm trường đơn vị để hiển thị trên giao diện cho rõ
    uom_id = fields.Many2one('uom.uom', 'Đơn vị', related='product_id.uom_id', readonly=True)

    reason = fields.Selection([
        ('burnt', 'Lỗi chế biến: Cháy/Hỏng'),
        ('raw_bad', 'Nguyên liệu hỏng'),
        ('accident', 'Rơi vỡ / Tai nạn'),
    ], string='Lý do', required=True, default='burnt')
    
    note = fields.Text('Ghi chú chi tiết')

    def action_confirm_scrap(self):
        """Tạo phiếu Scrap và HỦY LỆNH SẢN XUẤT"""
        self.ensure_one()
        StockScrap = self.env['stock.scrap']
        
        # 1. Logic tìm kho như cũ...
        scrap_location = self.env['stock.location'].search([('scrap_location', '=', True)], limit=1)
        if not scrap_location:
            raise UserError("Chưa cấu hình kho phế liệu!")

        if self.production_id:
            source_location = self.production_id.location_src_id.id
        else:
            source_location = self.env['stock.location'].search([('usage','=','internal')], limit=1).id
        
        # 2. Tạo phiếu Scrap (Ghi nhận mất mát)
        # Lưu ý: with_context(default_production_id=False) để tránh lỗi Odoo
        scrap = StockScrap.with_context(default_production_id=False).create({
            'product_id': self.product_id.id,
            'scrap_qty': self.qty,
            'product_uom_id': self.product_id.uom_id.id,
            'location_id': source_location,
            'scrap_location_id': scrap_location.id,
            'origin': self.production_id.name,
            'state': 'draft',
        })
        scrap.action_validate()
        
        # 3. [QUAN TRỌNG] CẬP NHẬT TRẠNG THÁI ĐƠN SX -> HỦY
        # Nếu lý do là lỗi nghiêm trọng (Cháy/Hỏng/Tai nạn), dừng quy trình ngay.
        if self.production_id and self.reason in ['burnt', 'accident', 'raw_bad']:
            self.production_id.write({'state': 'cancel'})
            
            # Ghi log màu đỏ
            self.production_id.message_post(
                body=f"<span style='color:red; font-weight:bold'>ĐƠN HÀNG ĐÃ BỊ HỦY DO SỰ CỐ:</span> "
                     f"{dict(self._fields['reason'].selection).get(self.reason)}"
            )

        return {'type': 'ir.actions.act_window_close'}
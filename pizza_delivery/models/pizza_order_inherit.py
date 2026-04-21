from odoo import models, fields, api, _

class PizzaSalesOrderInherit(models.Model):
    _inherit = 'pizza.sales.order'

    delivery_ids = fields.One2many('pizza.delivery.order', 'sales_order_id', string='Lịch sử giao vận')
    delivery_count = fields.Integer(compute='_compute_delivery_count')

    @api.depends('delivery_ids')
    def _compute_delivery_count(self):
        for rec in self:
            rec.delivery_count = len(rec.delivery_ids)

    # --- KẾ THỪA HÀM THANH TOÁN ---
    def action_payment(self):
        # 1. Chạy logic gốc (để kiểm tra tiền, món ăn...)
        res = super(PizzaSalesOrderInherit, self).action_payment()
        
        for order in self:
            # Chỉ xử lý nếu là đơn Giao hàng VÀ chưa tạo phiếu
            if order.order_type == 'delivery' and not order.delivery_ids:
                
                # --- LOGIC TÍNH TIỀN THU HỘ (COD) ---
                money_to_collect = 0.0
                if order.payment_method == 'cod':
                    money_to_collect = order.amount_total
                # Nếu payment_method == 'online' thì money_to_collect = 0.0
                
                # --- TẠO PHIẾU GIAO HÀNG ---
                self.env['pizza.delivery.order'].create({
                    'sales_order_id': order.id,
                    'address': order.delivery_address,
                    'priority': order.delivery_priority,
                    
                    # Truyền số tiền thu hộ đã tính vào đây
                    'amount_cod': money_to_collect, 
                    
                    'state': 'draft'
                })
                
                # Cập nhật trạng thái đơn hàng sang "Đang giao hàng"
                order.write({'state': 'delivering'})
                
                # Ghi log thông báo
                msg = f"🚚 Đã tạo phiếu giao hàng. Thu hộ: {money_to_collect:,.0f} đ"
                if money_to_collect == 0:
                    msg = "🚚 Đã tạo phiếu giao hàng. Khách đã thanh toán trước (Không thu COD)."
                order.message_post(body=msg)
        
        return res

    def action_view_deliveries(self):
        self.ensure_one()
        return {
            'name': 'Phiếu giao hàng',
            'type': 'ir.actions.act_window',
            'res_model': 'pizza.delivery.order',
            'view_mode': 'list,form',
            'domain': [('sales_order_id', '=', self.id)],
        }
    
    def action_create_delivery(self):
        """Nút tạo thủ công (dự phòng)"""
        self.ensure_one()
        
        # Tính lại COD cho chắc
        cod = self.amount_total if self.payment_method == 'cod' else 0.0
        
        self.env['pizza.delivery.order'].create({
            'sales_order_id': self.id,
            'address': self.delivery_address, 
            'amount_cod': cod,
            'state': 'draft'
        })
        
        # Cập nhật trạng thái
        self.write({'state': 'delivering'})
        
        return self.action_view_deliveries()
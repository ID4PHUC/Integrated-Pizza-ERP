# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime

class PizzaDeliveryOrder(models.Model):
    _name = 'pizza.delivery.order'
    _description = 'Phiếu Giao Hàng'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, date_created desc'

    # --- Header ---
    name = fields.Char('Mã vận đơn', default='New', readonly=True)
    
    # Liên kết với Đơn bán hàng gốc
    sales_order_id = fields.Many2one('pizza.sales.order', string='Đơn Pizza gốc', required=True, readonly=True)
    customer_id = fields.Many2one(related='sales_order_id.customer_id', string='Khách hàng', store=True)
    
    # Địa chỉ giao hàng (Cho phép sửa)
    address = fields.Char(related='sales_order_id.delivery_address', string='Địa chỉ giao', store=True, readonly=False)
    
    # --- TUYẾN ĐƯỜNG & TÀI XẾ ---
    route_id = fields.Many2one('pizza.delivery.route', string='Tuyến đường/Khu vực', 
                               help="Tự động nhận diện nếu tên Tuyến có trong Địa chỉ")
    
    # Trường ẩn: Chứa danh sách tài xế hợp lệ để lọc trên giao diện (cho Quản lý chọn)
    available_driver_ids = fields.Many2many('pizza.driver', compute='_compute_available_drivers')

    driver_id = fields.Many2one('pizza.driver', string='Tài xế', tracking=True)
    
    # --- LOGIC TÍNH TOÁN DANH SÁCH TÀI XẾ HỢP LỆ (Cho Quản lý) ---
    @api.depends('route_id')
    def _compute_available_drivers(self):
        for rec in self:
            domain = [('state', '=', 'available')]
            if rec.route_id:
                route_driver_ids = rec.route_id.driver_ids.ids
                if route_driver_ids:
                    domain.append(('id', 'in', route_driver_ids))
                else:
                    domain.append(('id', '=', -1)) 
            drivers = self.env['pizza.driver'].search(domain)
            rec.available_driver_ids = drivers.ids

    # --- CÁC TRƯỜNG KHÁC ---
    priority = fields.Selection([
        ('0', 'Thường'), ('1', 'Gấp'), ('2', 'Hỏa tốc')
    ], default='0', string='Độ ưu tiên', related='sales_order_id.delivery_priority', store=True, readonly=False)

    date_created = fields.Datetime('Thời gian tạo', default=fields.Datetime.now)
    date_done = fields.Datetime('Thời gian hoàn tất')
    amount_cod = fields.Float(string='Tiền thu hộ (COD)', default=0.0, help="Số tiền Shipper phải thu")
    
    state = fields.Selection([
        ('draft', 'Chờ điều phối'),
        ('assigned', 'Đã gán xe'),
        ('shipping', 'Đang giao hàng'),
        ('done', 'Giao thành công'),
        ('fail', 'Giao thất bại'),
        ('cancel', 'Hủy')
    ], default='draft', string='Tiến độ', tracking=True, group_expand='_expand_groups')

    customer_signature = fields.Binary('Chữ ký khách hàng')
    proof_photo = fields.Binary('Ảnh xác nhận')
    fail_reason = fields.Text('Lý do thất bại')

    # --- LOGIC 1: TỰ ĐỘNG TÌM TUYẾN TỪ ĐỊA CHỈ ---
    @api.onchange('address')
    def _onchange_address_find_route(self):
        if self.address:
            all_routes = self.env['pizza.delivery.route'].search([])
            found = False
            addr_lower = self.address.lower()
            for r in all_routes:
                if r.name.lower() in addr_lower:
                    self.route_id = r.id
                    found = True
                    break
            if not found:
                self.route_id = False

    # --- LOGIC 2: RESET TÀI XẾ KHI ĐỔI TUYẾN ---
    @api.onchange('route_id')
    def _onchange_route_id(self):
        if self.driver_id and self.driver_id.id not in self.available_driver_ids.ids:
            self.driver_id = False

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('pizza.delivery.order') or 'New'
        return super(PizzaDeliveryOrder, self).create(vals)

    @api.model
    def create_delivery_ticket(self, sales_order):
        running = self.search([('sales_order_id', '=', sales_order.id), ('state', 'not in', ['done', 'fail', 'cancel'])])
        if running: return running[0]
        
        cod = sales_order.amount_total if sales_order.payment_method == 'cod' else 0.0
        new_del = self.create({'sales_order_id': sales_order.id, 'amount_cod': cod, 'state': 'draft'})
        new_del._onchange_address_find_route()
        return new_del

    # --- [MỚI] HÀM CHO TÀI XẾ TỰ NHẬN ĐƠN ---
    def action_driver_take_order(self):
        """Tài xế bấm nút này để tự nhận đơn"""
        current_driver = self.env['pizza.driver'].search([('partner_id', '=', self.env.user.partner_id.id)], limit=1)
        
        if not current_driver:
            raise UserError(_("Tài khoản của bạn chưa liên kết với Hồ sơ Tài xế nào!"))
        
        if current_driver.state != 'available':
            raise UserError(_("Bạn đang bận hoặc nghỉ làm, không thể nhận đơn!"))

        self.write({
            'driver_id': current_driver.id,
            'state': 'assigned'
        })
        
        self.message_post(body=f"✋ Tài xế {current_driver.name} đã nhận đơn hàng này.")
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    # --- CÁC HÀM XỬ LÝ TRẠNG THÁI (Đã thêm sudo() để tránh lỗi Access Error) ---
    def action_assign(self):
        return {
            'name': _('Chọn Tài xế'),
            'type': 'ir.actions.act_window',
            'res_model': 'pizza.assign.driver.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_delivery_id': self.id}
        }

    def action_start_ship(self):
        if not self.driver_id: raise UserError(_("Chưa có tài xế!"))
        self.state = 'shipping'
        # [FIX] Dùng sudo() cho driver
        if self.driver_id:
            self.driver_id.sudo().write({'state': 'busy'})

    def action_confirm_done(self):
        if not self.proof_photo and not self.customer_signature: 
            raise UserError(_("Thiếu ảnh/chữ ký!"))
            
        self.state = 'done'
        self.date_done = datetime.now()
        
        # [FIX] Dùng sudo() cho driver
        if self.driver_id:
            self.driver_id.sudo().write({'state': 'available'})
            
        # [FIX QUAN TRỌNG] Dùng sudo() cho sales_order vì tài xế không có quyền sửa đơn hàng
        if self.sales_order_id.state != 'done': 
            self.sales_order_id.sudo().action_confirm_delivery_success()

    def action_fail(self):
        self.state = 'fail'
        
        # [FIX] Dùng sudo() cho driver
        if self.driver_id:
            self.driver_id.sudo().write({'state': 'available'})
            
        reason = self.fail_reason or "Shipper không ghi lý do"
        
        # [FIX QUAN TRỌNG] Dùng sudo() cho sales_order
        if self.sales_order_id: 
            self.sales_order_id.sudo().action_delivery_failed(reason)

    @api.model
    def _expand_groups(self, states, domain, order=None):
        return ['draft', 'assigned', 'shipping', 'done', 'fail']
# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class PizzaDriver(models.Model):
    _name = 'pizza.driver'
    _description = 'Hồ sơ Tài xế'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Tên tài xế', required=True, tracking=True)
    partner_id = fields.Many2one('res.partner', string='Liên kết User', help="Dùng để đăng nhập App")
    phone = fields.Char(related='partner_id.phone', string='Số điện thoại', readonly=False)
    
    # Thông tin xe (Nhập tay - đã sửa lỗi DatatypeMismatch)
    vehicle_id = fields.Char(string='Loại xe', help="Nhập tay thông tin xe (VD: Xe máy Honda Wave, Vios...)")
    
    # Biển số xe (Nhập tay)
    license_plate = fields.Char(string='Biển số xe')
    
    # KPI
    delivery_count = fields.Integer(string='Tổng đơn đã giao', compute='_compute_stats')
    
    rating = fields.Selection([
        ('0', '0 Sao'), ('1', '1 Sao'), ('2', '2 Sao'),
        ('3', '3 Sao'), ('4', '4 Sao'), ('5', '5 Sao')
    ], string='Đánh giá trung bình', default='5', tracking=True)
    
    state = fields.Selection([
        ('available', 'Đang rảnh'),
        ('busy', 'Đang đi giao'),
        ('offline', 'Nghỉ làm')
    ], default='available', string='Trạng thái', tracking=True)

    # --- LIÊN KẾT: Lịch sử xin nghỉ ---
    leave_request_ids = fields.One2many('pizza.driver.leave.request', 'driver_id', string='Lịch sử xin nghỉ')

    def _compute_stats(self):
        for rec in self:
            if self.env['ir.model']._get('pizza.delivery.order'):
                rec.delivery_count = self.env['pizza.delivery.order'].search_count([
                    ('driver_id', '=', rec.id),
                    ('state', '=', 'done')
                ])
            else:
                rec.delivery_count = 0

# ========================================================
# MODEL MỚI: YÊU CẦU XIN NGHỈ (LEAVE REQUEST)
# ========================================================
class PizzaDriverLeaveRequest(models.Model):
    _name = 'pizza.driver.leave.request'
    _description = 'Yêu cầu xin nghỉ của Tài xế'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string="Mã phiếu", default="Mới", readonly=True)
    
    driver_id = fields.Many2one('pizza.driver', string="Tài xế", required=True, 
                                default=lambda self: self._default_driver())
    
    date_from = fields.Date(string="Nghỉ từ ngày", required=True, default=fields.Date.today)
    date_to = fields.Date(string="Đến ngày", required=True, default=fields.Date.today)
    reason = fields.Text(string="Lý do", required=True)
    
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('confirm', 'Chờ duyệt'),
        ('approved', 'Đã duyệt'),
        ('refused', 'Từ chối'),
        ('cancel', 'Hủy')
    ], default='draft', string="Trạng thái", tracking=True)

    # Tự động lấy tài xế dựa trên user đang đăng nhập
    def _default_driver(self):
        return self.env['pizza.driver'].search([('partner_id', '=', self.env.user.partner_id.id)], limit=1)

    @api.model
    def create(self, vals):
        if vals.get('name', 'Mới') == 'Mới':
            vals['name'] = self.env['ir.sequence'].next_by_code('pizza.driver.leave') or 'LEAVE'
        return super(PizzaDriverLeaveRequest, self).create(vals)

    def action_confirm(self):
        self.state = 'confirm'

    # --- LOGIC QUAN TRỌNG: DUYỆT -> CHUYỂN TRẠNG THÁI OFFLINE ---
    def action_approve(self):
        for rec in self:
            rec.state = 'approved'
            if rec.driver_id:
                # Chuyển tài xế sang Offline
                rec.driver_id.state = 'offline'
                # Ghi chú vào hồ sơ tài xế
                rec.driver_id.message_post(body=f"⚠️ Tài xế chuyển sang trạng thái NGHỈ LÀM do phiếu {rec.name} đã được duyệt.")

    def action_refuse(self):
        self.state = 'refused'

    def action_draft(self):
        self.state = 'draft'
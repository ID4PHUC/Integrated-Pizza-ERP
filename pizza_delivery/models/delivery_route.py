# -*- coding: utf-8 -*-
from odoo import models, fields, api

class PizzaDeliveryRoute(models.Model):
    _name = 'pizza.delivery.route'
    _description = 'Tuyến đường / Khu vực giao hàng'
    _order = 'name'

    name = fields.Char(string='Tên Tuyến/Khu vực', required=True, help="VD: Khu vực Quận 1, Tuyến Phố Cổ")
    code = fields.Char(string='Mã định danh', required=True)
    description = fields.Text(string='Mô tả chi tiết')
    
    # Một tuyến đường có thể có nhiều tài xế phụ trách
    driver_ids = fields.Many2many('pizza.driver', string='Tài xế phụ trách')
    
    # Phí ship dự kiến cho khu vực này
    estimated_shipping_fee = fields.Float(string='Phí ship trung bình', default=15000)

    active = fields.Boolean(default=True)

class PizzaDeliveryOrderRoute(models.Model):
    _inherit = 'pizza.delivery.order'

    # Thêm trường Route vào phiếu giao hàng
    route_id = fields.Many2one('pizza.delivery.route', string='Tuyến đường')
    
    @api.onchange('route_id')
    def _onchange_route_id(self):
        # Khi chọn tuyến, gợi ý phí ship (nếu cần)
        if self.route_id:
            pass # Có thể viết logic gán phí ship vào đơn gốc tại đây
# -*- coding: utf-8 -*-
from odoo import models, fields, api

class AssignDriverWizard(models.TransientModel):
    _name = 'pizza.assign.driver.wizard'
    _description = 'Chọn tài xế nhanh'

    delivery_id = fields.Many2one('pizza.delivery.order', required=True)
    
    # [MỚI] Trường ẩn: Chứa danh sách tài xế hợp lệ (để lọc trên giao diện)
    available_driver_ids = fields.Many2many('pizza.driver', compute='_compute_available_drivers')

    # Trường chọn tài xế
    driver_id = fields.Many2one('pizza.driver', string='Chọn Tài xế', required=True)
    note = fields.Text(string='Ghi chú giao hàng')

    @api.depends('delivery_id')
    def _compute_available_drivers(self):
        for rec in self:
            # 1. Điều kiện tiên quyết: Tài xế phải đang rảnh
            domain = [('state', '=', 'available')]
            
            # 2. Nếu đơn hàng có Tuyến đường -> Thêm điều kiện lọc theo Tuyến
            if rec.delivery_id.route_id:
                route_driver_ids = rec.delivery_id.route_id.driver_ids.ids
                if route_driver_ids:
                    domain.append(('id', 'in', route_driver_ids))
                else:
                    # Nếu tuyến đường này chưa gán ai -> Không cho chọn ai cả
                    domain.append(('id', '=', -1))
            
            # 3. Tìm tài xế thỏa mãn và gán vào biến phụ
            drivers = self.env['pizza.driver'].search(domain)
            rec.available_driver_ids = drivers.ids

    def action_confirm_assign(self):
        # Cập nhật thông tin vào phiếu giao hàng
        self.delivery_id.write({
            'driver_id': self.driver_id.id,
            'state': 'assigned'
        })
        
        # Ghi log tin nhắn
        if self.note:
            self.delivery_id.message_post(body=f"📌 Điều phối viên ghi chú: {self.note}")
            
        # Đóng wizard và reload lại trang phía sau để thấy thay đổi
        return {
            'type': 'ir.actions.act_window_close',
            'infos': {'reload': True} # Yêu cầu reload giao diện
        }
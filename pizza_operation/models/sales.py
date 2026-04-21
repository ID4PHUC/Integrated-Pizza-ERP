# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class PizzaSalesOrder(models.Model):
    _name = 'pizza.sales.order'
    _description = '3.4.3.4 - Đơn bán hàng Pizza'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # =========================================================
    # 1. THÔNG TIN CƠ BẢN & KHÁCH HÀNG
    # =========================================================
    name = fields.Char('Mã đơn', default='Mới', readonly=True)
    customer_id = fields.Many2one('res.partner', 'Khách hàng', required=True)
    date_order = fields.Datetime('Ngày đặt', default=fields.Datetime.now)

    # =========================================================
    # 2. CẤU HÌNH GIAO HÀNG (DELIVERY) & THANH TOÁN
    # =========================================================
    order_type = fields.Selection([
        ('dine_in', 'Ăn tại quán'),
        ('delivery', 'Giao hàng tận nơi')
    ], string='Hình thức', default='dine_in', required=True, tracking=True)

    # Các trường thông tin giao hàng
    delivery_address = fields.Char(string='Địa chỉ giao', tracking=True, 
                                   help="Địa chỉ giao hàng cho Shipper")
    
    delivery_priority = fields.Selection([
        ('0', 'Thường'), 
        ('1', 'Gấp'), 
        ('2', 'Hỏa tốc')
    ], string='Ưu tiên', default='0')

    payment_method = fields.Selection([
        ('cod', 'Tiền mặt khi nhận (COD)'),
        ('online', 'Chuyển khoản / Đã thanh toán')
    ], string='Thanh toán', default='cod',
      help="COD: Shipper thu tiền. Online: Shipper không thu.")

    # Tự động điền địa chỉ khi chọn khách hàng
    @api.onchange('customer_id', 'order_type')
    def _onchange_delivery_info(self):
        if self.order_type == 'delivery' and self.customer_id:
            self.delivery_address = self.customer_id.contact_address or ''
        elif self.order_type == 'dine_in':
            self.delivery_address = False
            self.payment_method = False

    # =========================================================
    # 3. CHI TIẾT ĐƠN HÀNG & TRẠNG THÁI (STATE)
    # =========================================================
    line_ids = fields.One2many('pizza.sales.line', 'order_id', string='Chi tiết đơn hàng')
    amount_total = fields.Float('Tổng tiền', compute='_compute_total', store=True)
    
    warehouse_id = fields.Many2one('stock.warehouse', 'Kho hàng', 
                                   default=lambda self: self.env['stock.warehouse'].search([], limit=1))

    # [QUAN TRỌNG] State đã thêm 'fail' để tách biệt logic Giao thất bại
    state = fields.Selection([
        ('draft', 'Chọn món'),
        ('waiting', 'Chờ hàng (Backorder)'),
        ('checked', 'Đủ hàng (Chờ thanh toán)'),
        ('delivering', 'Đang giao hàng'),       # Shipper đang đi
        ('fail', 'Giao thất bại'),              # Shipper báo lỗi (Chờ xử lý lại)
        ('done', 'Giao thành công'),            # Hoàn tất
        ('cancel', 'Hủy đơn'),
        ('refund', 'Đã hoàn tiền'),
    ], default='draft', string='Trạng thái', tracking=True)

    @api.depends('line_ids.subtotal')
    def _compute_total(self):
        for order in self:
            order.amount_total = sum(order.line_ids.mapped('subtotal'))

    @api.model
    def create(self, vals):
        if vals.get('name', 'Mới') == 'Mới':
            vals['name'] = self.env['ir.sequence'].next_by_code('pizza.sales.order') or 'Mới'
        return super(PizzaSalesOrder, self).create(vals)

    # =========================================================
    # 4. CÁC HÀNH ĐỘNG (BUTTONS) - LOGIC CHÍNH
    # =========================================================
    
    # --- 4.1 Kiểm tra kho ---
    def action_check_stock(self):
        if not self.line_ids: raise UserError(_("Vui lòng chọn món trước!"))
        
        missing = []
        for line in self.line_ids:
            if line.product_id.qty_available < line.qty:
                missing.append(line.product_id.name)
        
        if missing:
            return {
                'type': 'ir.actions.client', 'tag': 'display_notification', 
                'params': {'title': 'Thiếu hàng', 'message': f"Thiếu: {', '.join(missing)}", 'type': 'danger', 'sticky': True}
            }
        self.state = 'checked'
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    # --- 4.2 Khách chờ (Backorder) ---
    def action_create_backorder(self):
        self.state = 'waiting'

    # --- 4.3 THANH TOÁN / XÁC NHẬN ---
    def action_payment(self):
        """Logic phân luồng: Tại quán vs Giao hàng"""
        if not self.line_ids: raise UserError("Đơn hàng trống!")
        if self.amount_total == 0: raise UserError("Tổng tiền bằng 0!")

        msg = ""
        if self.order_type == 'dine_in':
            # Ăn tại quán: Trừ kho ngay -> Done
            self._create_picking_out()
            self.state = 'done'
            msg = "Đã thanh toán và hoàn tất (Tại quán)!"
        else:
            # Giao hàng: Chuyển sang 'delivering'
            self.state = 'delivering'
            msg = "Đã xác nhận! Đơn hàng đang được giao."
            
            # [THÊM DÒNG NÀY] Tạo phiếu giao hàng bên module Delivery
            self.env['pizza.delivery.order'].create_delivery_ticket(self)

        return {'effect': {'fadeout': 'slow', 'message': msg, 'type': 'rainbow_man'}}
    
    
    def action_retry_delivery(self):
        """Cho phép giao lại đơn hàng đã bị thất bại trước đó"""
        if self.state != 'fail':
             raise UserError(_("Chỉ có thể giao lại các đơn hàng đang ở trạng thái 'Giao thất bại'!"))
        
        # Đẩy trạng thái về Đang giao để Shipper thấy lại đơn này
        self.state = 'delivering'
        
        # [THÊM DÒNG NÀY] Tạo một phiếu giao hàng MỚI cho lần thử lại này
        self.env['pizza.delivery.order'].create_delivery_ticket(self)
        
        # Ghi log
        self.message_post(body="🔄 <b>Yêu cầu giao lại:</b> Đã tạo phiếu vận đơn mới và chuyển trạng thái sang Đang giao hàng.")
        return {'type': 'ir.actions.client', 'tag': 'reload'}
    
    # --- 4.5 CALLBACK: SHIPPER GIAO THÀNH CÔNG ---
    def action_confirm_delivery_success(self):
        """Được gọi từ module pizza_delivery khi shipper bấm Done"""
        if self.state != 'done':
            self._create_picking_out() # Lúc này mới thực sự trừ kho
            self.state = 'done'
            self.message_post(body="✅ Shipper xác nhận giao thành công. Đã trừ kho.")

    # --- 4.6 CALLBACK: SHIPPER GIAO THẤT BẠI ---
    def action_delivery_failed(self, reason):
        """Được gọi từ module pizza_delivery khi shipper bấm Fail."""
        if self.state == 'delivering':
            self.state = 'fail' # Chuyển về trạng thái Fail để chờ xử lý
            
            self.message_post(body=f"""
                <div style="background-color: #ffdddd; border-left: 6px solid #f44336; padding: 10px;">
                    <strong>❌ GIAO HÀNG THẤT BẠI!</strong><br/>
                    Lý do shipper báo về: {reason}<br/>
                    <em>Đơn hàng đã được trả về trạng thái 'Giao thất bại'. Vui lòng chọn 'Giao lại' hoặc 'Hoàn tiền'.</em>
                </div>
            """)
            return True
        return False

    # --- 4.7 Yêu cầu sản xuất ---
    def action_request_production(self):
        PizzaProduction = self.env['pizza.production.order']
        created_mos = 0
        for line in self.line_ids:
            if line.product_id.qty_available < line.qty:
                PizzaProduction.create({
                    'pizza_id': line.product_id.id,
                    'qty_producing': line.qty - line.product_id.qty_available,
                    'date_planned': fields.Datetime.now(),
                    'origin': self.name,
                })
                created_mos += 1
        
        if created_mos > 0:
            return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {'title': 'Thành công', 'message': f'Đã tạo {created_mos} lệnh SX', 'type': 'success'}}
        raise UserError("Kho đủ hàng, không cần SX!")

    # --- 4.8 LOGIC HOÀN TIỀN / HỦY ĐƠN (ĐÃ SỬA LOGIC) ---
    def action_refund(self):
        """Xử lý hoàn tiền cho cả 2 trường hợp: Chưa trừ kho & Đã trừ kho"""
        
        # TRƯỜNG HỢP 1: Giao thất bại (Fail) -> Hàng chưa xuất kho -> Chỉ cần đổi trạng thái
        if self.state == 'fail':
            self.state = 'refund'
            self.message_post(body="⛔ Đã Hủy đơn & Hoàn tiền (Hàng chưa xuất kho).")
            return {
                'effect': {
                    'fadeout': 'slow', 
                    'message': 'Đã hoàn tiền và Hủy đơn (Hàng chưa xuất)!', 
                    'type': 'rainbow_man'
                }
            }

        # TRƯỜNG HỢP 2: Đã giao xong/Ăn xong (Done) -> Hàng đã trừ kho -> Phải làm phiếu nhập trả
        if self.state == 'done':
            lines_refund = self.line_ids.filtered(lambda l: l.qty_to_refund > 0)
            if not lines_refund: 
                raise UserError(_("Vui lòng nhập số lượng trả > 0 vào danh sách món!"))

            StockPicking = self.env['stock.picking']
            picking_type = self.warehouse_id.in_type_id
            
            picking = StockPicking.create({
                'picking_type_id': picking_type.id,
                'location_id': self.env.ref('stock.stock_location_customers').id,
                'location_dest_id': picking_type.default_location_dest_id.id,
                'origin': f"Trả hàng: {self.name}",
                'partner_id': self.customer_id.id,
            })
            self._create_move_and_validate(picking, is_refund=True, lines=lines_refund)
            self.state = 'refund'
            
            return {
                'effect': {
                    'fadeout': 'slow', 
                    'message': 'Đã nhập kho hàng trả và Hoàn tiền!', 
                    'type': 'rainbow_man'
                }
            }
        
        raise UserError("Trạng thái đơn hàng không hợp lệ để hoàn tiền!")

    # --- 4.9 Nút thủ công (nếu cần test) ---
    def action_deliver(self):
        return self.action_confirm_delivery_success()

    # =========================================================
    # 5. HÀM HỖ TRỢ KHO
    # =========================================================
    def _create_picking_out(self):
        StockPicking = self.env['stock.picking']
        picking_type = self.warehouse_id.out_type_id
        
        # Tạo phiếu kho (chưa validate)
        picking = StockPicking.create({
            'picking_type_id': picking_type.id,
            'location_id': picking_type.default_location_src_id.id, 
            'location_dest_id': self.env.ref('stock.stock_location_customers').id, 
            'origin': self.name,
            'partner_id': self.customer_id.id,
        })
        self._create_move_and_validate(picking, is_refund=False)

    def _create_move_and_validate(self, picking, is_refund=False, lines=None):
        """Hàm này đã được Fix để không bị nhân đôi số lượng trừ kho"""
        StockMove = self.env['stock.move']
        
        target_lines = lines or self.line_ids
        for line in target_lines:
            qty = line.qty_to_refund if is_refund else line.qty
            if qty <= 0: continue
            
            # 1. Tạo Move
            move = StockMove.create({
                'name': line.product_id.name, 
                'product_id': line.product_id.id,
                'product_uom_qty': qty, 
                'product_uom': line.product_id.uom_id.id,
                'picking_id': picking.id, 
                'location_id': picking.location_id.id,
                'location_dest_id': picking.location_dest_id.id,
            })
            
            # 2. Confirm & Assign (Đặt trước hàng)
            move._action_confirm()
            move._action_assign()
            
            # [FIX QUAN TRỌNG] Gán số lượng thực tế trực tiếp vào move.quantity
            # Tuyệt đối KHÔNG dùng StockMoveLine.create ở đây nữa
            move.quantity = qty
            
            # 3. Đánh dấu đã nhặt
            move.picked = True
            
        # 4. Hoàn tất phiếu kho
        picking.with_context(skip_immediate=True, skip_backorder=True).button_validate()

# =========================================================
# 6. CLASS CHI TIẾT MÓN ĂN
# =========================================================
class PizzaSalesLine(models.Model):
    _name = 'pizza.sales.line'
    _description = 'Chi tiết món ăn'
    
    order_id = fields.Many2one('pizza.sales.order')
    product_id = fields.Many2one('product.product', 'Món', domain="[('sale_ok','=',True)]", required=True)
    qty_available = fields.Float('Tồn kho', related='product_id.qty_available')
    
    qty = fields.Float('Số lượng mua', default=1.0)
    qty_to_refund = fields.Float('Số lượng trả', default=0.0)
    
    price_unit = fields.Float('Đơn giá', related='product_id.list_price')
    subtotal = fields.Float('Thành tiền', compute='_compute_subtotal')
    
    @api.depends('qty', 'price_unit')
    def _compute_subtotal(self):
        for line in self: 
            line.subtotal = line.qty * line.price_unit
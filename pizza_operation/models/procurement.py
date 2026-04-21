from odoo import models, fields, api, _
from odoo.exceptions import UserError

class PizzaPurchaseRequest(models.Model):
    _name = 'pizza.procurement.request'
    _description = 'Phiếu Yêu cầu Nhập nguyên liệu'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # --- THÔNG TIN CHUNG ---
    name = fields.Char(
        string='Mã phiếu', 
        default='Mới', 
        readonly=True, 
        copy=False
    )
    
    requester_id = fields.Many2one(
        'res.users', string='Người yêu cầu', 
        default=lambda self: self.env.user, readonly=True
    )
    
    vendor_id = fields.Many2one(
        'res.partner', string='Nhà cung cấp', 
        domain="[('supplier_rank','>',0)]", required=True,
        tracking=True,
        help="Chọn nhà cung cấp dự kiến mua hàng"
    )
    
    warehouse_id = fields.Many2one(
        'stock.warehouse', string='Kho nhận hàng', 
        required=True
    )
    
    date_planned = fields.Date(
        string='Ngày cần hàng', 
        default=fields.Date.context_today, 
        required=True,
        help="Ngày dự kiến nguyên liệu phải về tới kho"
    )
    
    note = fields.Text(string='Ghi chú / Lý do điều chỉnh')

    line_ids = fields.One2many(
        'pizza.procurement.line', 'request_id', 
        string='Danh sách nguyên liệu'
    )
    
    # --- TRẠNG THÁI (TIẾNG VIỆT) ---
    state = fields.Selection([
        ('draft', 'Nháp (Đang soạn)'),
        ('confirm', 'Chờ duyệt'),
        ('approved', 'Đã duyệt (Chờ mua)'),
        ('done', 'Hoàn tất (Đã tạo PO)'),
    ], default='draft', string='Trạng thái', tracking=True)

    # --- CÁC TRƯỜNG ĐẾM (CHO SMART BUTTON) ---
    purchase_count = fields.Integer(string='Đơn mua hàng', compute='_compute_purchase_count')
    picking_count = fields.Integer(string='Phiếu nhập kho', compute='_compute_picking_count')

    # --- LOGIC TÍNH TOÁN ---

    def _compute_purchase_count(self):
        for record in self:
            record.purchase_count = self.env['purchase.order'].search_count([('origin', '=', record.name)])

    def _compute_picking_count(self):
        for record in self:
            related_pos = self.env['purchase.order'].search([('origin', '=', record.name)])
            if related_pos:
                pickings = related_pos.mapped('picking_ids')
                record.picking_count = len(pickings)
            else:
                record.picking_count = 0

    @api.model
    def create(self, vals):
        if vals.get('name', 'Mới') == 'Mới':
            vals['name'] = self.env['ir.sequence'].next_by_code('pizza.procurement.request') or 'Mới'
        return super(PizzaPurchaseRequest, self).create(vals)

    # --- CÁC NÚT BẤM (ACTION) ---

    def action_confirm(self):
        if not self.line_ids:
            raise UserError(_('Vui lòng nhập ít nhất một dòng nguyên liệu trước khi gửi duyệt.'))
        self.state = 'confirm'

    def action_approve(self):
        self.state = 'approved'

    def action_draft(self):
        self.state = 'draft'

    def action_create_po(self):
        self.ensure_one()
        purchase_obj = self.env['purchase.order']
        
        # Chuẩn bị dữ liệu tạo PO
        po_vals = {
            'partner_id': self.vendor_id.id,
            'date_order': self.date_planned,
            'picking_type_id': self.warehouse_id.in_type_id.id,
            'origin': self.name,
            'order_line': []
        }

        for line in self.line_ids:
            po_vals['order_line'].append((0, 0, {
                'product_id': line.product_id.id,
                'product_qty': line.qty,
                'product_uom': line.uom_id.id,
                'price_unit': line.product_id.standard_price,
                'date_planned': self.date_planned,
            }))

        po = purchase_obj.create(po_vals)
        self.state = 'done'
        
        # Thông báo lên tường chat
        msg = _("Đã tạo thành công Đơn mua hàng số %s. Vui lòng kiểm tra và gửi cho Nhà cung cấp.") % po.name
        self.message_post(body=msg)
        
        # Mở ngay đơn mua hàng vừa tạo
        return self.action_view_po()

    def action_view_po(self):
        self.ensure_one()
        return {
            'name': _('Danh sách Đơn mua hàng'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('origin', '=', self.name)],
            'context': {'default_origin': self.name},
        }
    
    
    def action_view_picking(self):
        self.ensure_one()
        related_pos = self.env['purchase.order'].search([('origin', '=', self.name)])
        pickings = related_pos.mapped('picking_ids')
        return {
            'name': _('Phiếu nhập kho'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [('id', 'in', pickings.ids)],
            'context': {'create': False},
        }


class PizzaProcurementLine(models.Model):
    _name = 'pizza.procurement.line'
    _description = 'Chi tiết dòng nguyên liệu'
    
    request_id = fields.Many2one('pizza.procurement.request')
    
    product_id = fields.Many2one(
        'product.product', string='Nguyên liệu', 
        domain="[('purchase_ok','=',True)]", required=True
    )

    # --- CÁC TRƯỜNG HIỂN THỊ THÔNG TIN (RELATED) ---
    product_image = fields.Binary(
        related='product_id.image_128', 
        string='Ảnh minh họa', 
        readonly=True
    )
    

    product_code = fields.Char(
        related='product_id.default_code', 
        string='Mã nội bộ', 
        readonly=True
    )


    storage_category = fields.Selection(
        related='product_id.product_tmpl_id.storage_category',
        string='Khu vực kho',
        readonly=False, # <--- Cho phép sửa trực tiếp
        store=True # <--- Lưu lại vào database để lọc/tìm kiếm nhanh hơn
    )
    
    qty_on_hand = fields.Float(
        string='Tồn kho hiện tại', 
        related='product_id.qty_available',
        readonly=True
    )
    

    qty = fields.Float(string='Số lượng mua', default=1.0, required=True)
    uom_id = fields.Many2one('uom.uom', string='Đơn vị tính', required=True)


    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            # Tự động lấy đơn vị mua hàng
            self.uom_id = self.product_id.uom_po_id or self.product_id.uom_id
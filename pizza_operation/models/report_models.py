# -*- coding: utf-8 -*-
from odoo import models, fields, tools

# =========================================================
# 1. BÁO CÁO NHẬP LIỆU (PROCUREMENT)
# =========================================================
class PizzaReportProcurement(models.Model):
    _name = "pizza.report.procurement"
    _description = "Thống kê Nhu cầu Nhập liệu"
    _auto = False
    _order = 'date_planned desc'

    date_planned = fields.Date('Ngày cần hàng', readonly=True)
    vendor_id = fields.Many2one('res.partner', 'Nhà cung cấp', readonly=True)
    product_id = fields.Many2one('product.product', 'Nguyên liệu', readonly=True)
    warehouse_id = fields.Many2one('stock.warehouse', 'Kho nhận', readonly=True)
    
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('confirm', 'Chờ duyệt'),
        ('approved', 'Đã duyệt'),
        ('done', 'Hoàn tất'),
    ], string='Trạng thái', readonly=True)

    qty = fields.Float('Số lượng yêu cầu', readonly=True)
    request_count = fields.Integer('Số phiếu', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW pizza_report_procurement AS (
                SELECT
                    l.id as id,
                    r.date_planned as date_planned,
                    r.vendor_id as vendor_id,
                    r.warehouse_id as warehouse_id,
                    r.state as state,
                    l.product_id as product_id,
                    l.qty as qty,
                    1 as request_count
                FROM
                    pizza_procurement_line l
                    JOIN pizza_procurement_request r ON (l.request_id = r.id)
            )
        """)

# =========================================================
# 2. BÁO CÁO KHO & HẠN DÙNG (STORAGE)
# =========================================================
class PizzaReportStorage(models.Model):
    _name = "pizza.report.storage"
    _description = "Báo cáo Tồn kho & Hạn dùng"
    _auto = False

    product_id = fields.Many2one('product.product', 'Sản phẩm', readonly=True)
    location_id = fields.Many2one('stock.location', 'Vị trí kho', readonly=True)
    lot_id = fields.Many2one('stock.lot', 'Lô/Serial', readonly=True)
    
    storage_category = fields.Selection([
        ('raw', 'Nguyên liệu thô'),
        ('cold', 'Kho lạnh'),
        ('finished', 'Thành phẩm'),
        ('packing', 'Đóng gói'),
    ], string='Khu vực', readonly=True)

    expiration_date = fields.Datetime('Ngày hết hạn', readonly=True)
    
    expiry_status = fields.Selection([
        ('expired', 'Đã hết hạn'),
        ('valid', 'Còn hạn'),
        ('no_date', 'Không có hạn'),
    ], string='Trạng thái Hạn', readonly=True)

    quantity = fields.Float('Tồn kho thực tế', readonly=True)
    # Giá trị tạm tính theo giá vốn (Standard Price)
    value = fields.Float('Giá trị tồn kho', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW pizza_report_storage AS (
                SELECT
                    min(q.id) as id,
                    q.product_id as product_id,
                    q.location_id as location_id,
                    q.lot_id as lot_id,
                    t.storage_category as storage_category,
                    l.expiration_date as expiration_date,
                    sum(q.quantity) as quantity,
                    
                    -- Tính giá trị: Số lượng * Giá niêm yết (List Price) hoặc Giá vốn (Standard Price)
                    -- Ở đây dùng list_price từ template cho đơn giản hóa logic
                    (sum(q.quantity) * t.list_price) as value,

                    CASE 
                        WHEN l.expiration_date IS NULL THEN 'no_date'
                        WHEN l.expiration_date < NOW() THEN 'expired'
                        ELSE 'valid'
                    END as expiry_status
                FROM
                    stock_quant q
                    JOIN product_product p ON (q.product_id = p.id)
                    JOIN product_template t ON (p.product_tmpl_id = t.id)
                    LEFT JOIN stock_lot l ON (q.lot_id = l.id)
                    JOIN stock_location loc ON (q.location_id = loc.id)
                WHERE
                    loc.usage = 'internal'
                GROUP BY
                    q.product_id, q.location_id, q.lot_id, t.storage_category, l.expiration_date, t.list_price
                HAVING 
                    sum(q.quantity) > 0
            )
        """)

# =========================================================
# 3. BÁO CÁO SẢN XUẤT (PRODUCTION)
# =========================================================
class PizzaReportProduction(models.Model):
    _name = "pizza.report.production"
    _description = "Thống kê Sản xuất"
    _auto = False
    _order = 'date_planned desc'

    date_planned = fields.Datetime('Ngày SX', readonly=True)
    pizza_id = fields.Many2one('product.product', 'Loại Pizza', readonly=True)
    user_id = fields.Many2one('res.users', 'Bếp trưởng', readonly=True)
    
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('confirmed', 'Đã xác nhận'),
        ('progress', 'Đang chế biến'),
        ('qc_check', 'Kiểm tra QC'),
        ('done', 'Hoàn thành'),
        ('cancel', 'Hủy'),
    ], string='Tiến độ', readonly=True)

    qty_producing = fields.Float('Số lượng làm', readonly=True)
    order_count = fields.Integer('Số lệnh', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW pizza_report_production AS (
                SELECT
                    id as id,
                    date_planned,
                    pizza_id,
                    user_id,
                    state,
                    qty_producing,
                    1 as order_count
                FROM
                    pizza_production_order
            )
        """)

# =========================================================
# 4. BÁO CÁO BÁN HÀNG (SALES)
# =========================================================
class PizzaReportSales(models.Model):
    _name = "pizza.report.sales"
    _description = "Phân tích Doanh thu"
    _auto = False
    _order = 'date desc'

    date = fields.Datetime('Ngày bán', readonly=True)
    product_id = fields.Many2one('product.product', 'Món ăn', readonly=True)
    customer_id = fields.Many2one('res.partner', 'Khách hàng', readonly=True)
    
    # Các trường mới từ module Pizza
    order_type = fields.Selection([
        ('dine_in', 'Ăn tại quán'),
        ('delivery', 'Giao hàng tận nơi')
    ], string='Hình thức', readonly=True)
    
    payment_method = fields.Selection([
        ('cod', 'Tiền mặt (COD)'),
        ('online', 'Chuyển khoản')
    ], string='Thanh toán', readonly=True)

    qty = fields.Float('Số lượng bán', readonly=True)
    amount = fields.Float('Doanh thu (VNĐ)', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        
        # [QUAN TRỌNG] Do 'subtotal' không lưu trong DB (store=True thiếu),
        # Ta phải tính toán lại bằng: qty * product_template.list_price
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW pizza_report_sales AS (
                SELECT
                    l.id as id,
                    s.date_order as date,
                    l.product_id as product_id,
                    s.customer_id as customer_id,
                    s.order_type as order_type,
                    s.payment_method as payment_method,
                    l.qty as qty,
                    
                    -- Tính doanh thu: Số lượng * Giá niêm yết sản phẩm
                    (l.qty * t.list_price) as amount

                FROM
                    pizza_sales_line l
                    JOIN pizza_sales_order s ON (l.order_id = s.id)
                    JOIN product_product p ON (l.product_id = p.id)
                    JOIN product_template t ON (p.product_tmpl_id = t.id)
                WHERE
                    s.state IN ('paid', 'done', 'checked', 'delivering')
            )
        """)

# =========================================================
# 5. BÁO CÁO HỦY HÀNG (SCRAP)
# =========================================================
class PizzaReportScrap(models.Model):
    _name = "pizza.report.scrap"
    _description = "Thống kê Hủy/Hỏng"
    _auto = False
    _order = 'date desc'

    date = fields.Datetime('Ngày ghi nhận', readonly=True)
    product_id = fields.Many2one('product.product', 'Sản phẩm lỗi', readonly=True)
    
    reason = fields.Selection([
        ('burnt', 'Lỗi chế biến: Cháy/Hỏng'),
        ('raw_bad', 'Nguyên liệu hỏng'),
        ('accident', 'Rơi vỡ / Tai nạn'),
    ], string='Lý do', readonly=True)
    
    qty = fields.Float('Số lượng mất', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW pizza_report_scrap AS (
                SELECT
                    id as id,
                    create_date as date,
                    product_id,
                    reason,
                    qty
                FROM
                    pizza_scrap_record
            )
        """)
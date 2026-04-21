# -*- coding: utf-8 -*-
{
    'name': "Quản lý Vận hành Pizza",
    'summary': "Hệ thống quản lý Nhập liệu, Kho và Sản xuất Pizza",
    'description': """
        Module bao gồm 3 quy trình chính:
        1. Nhập nguyên liệu (Procurement/Receipts) - Tạo yêu cầu mua hàng.
        2. Lưu kho (Storage) - Phân loại kho lạnh/nguyên liệu, quản lý hạn dùng.
        3. Sản xuất (Manufacturing) - Lệnh sản xuất Pizza từ BOM.
        4. Quản lý Chất lượng & Hủy hàng (Scrap).
        5. Bán hàng Pizza (Sales) - Tạo đơn hàng bán pizza cho khách hàng.
    """,
    'author': "Your Name",
    'website': "https://www.yourcompany.com",
    'category': 'Operations/Inventory',
    'version': '18.0.1.0.0',
    
    # Các module phụ thuộc bắt buộc phải có
    'depends': [
        'base', 
        'stock',     # Để dùng Warehouse, Location, Quant
        'product',   # Để dùng Product Template
        'purchase',  # Để tạo PO từ yêu cầu
        'mrp',       # Để dùng BOM (mrp.bom)
        'mail',       # Để dùng tính năng chat/log (chatter)
        'product_expiry',  # <--- BẮT BUỘC THÊM: Để quản lý Hạn sử dụng (FEFO)
    ],

    # Danh sách các file dữ liệu
    'data': [
        # 1. Phân quyền (Luôn load đầu tiên)
        'security/pizza_security.xml',
        'security/ir.model.access.csv',
        
        # 2. Dữ liệu khởi tạo (Sequence mã tự động)
        'data/sequence.xml',
        'data/ir_sequence_data.xml',
        'data/stock_data.xml',  # <-- Dữ liệu kho ban đầu
        
        # 3. Các file giao diện chức năng (Load trước Menu)
        'views/procurement_views.xml',
        'views/storage_views.xml',
        'views/production_views.xml',
        'views/quality_views.xml',
        'views/sales_views.xml',
        
        # 4. Menu 
        'views/menu_views.xml',
        'views/report_views.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False,
}
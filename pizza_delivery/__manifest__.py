# -*- coding: utf-8 -*-
{
    'name': "Pizza Delivery Pro",
    'summary': "Hệ thống quản lý đội ngũ giao hàng Pizza chuyên nghiệp",
    'description': """
        Module mở rộng cho Pizza Operation:
        - Quản lý hồ sơ Shipper, tích hợp xe cộ (Fleet).
        - Theo dõi quy trình giao hàng: Soạn -> Đang giao -> Thành công/Thất bại.
        - Giao diện Kanban kéo thả đơn hàng.
        - Tính năng 'Smart Assign' phân đơn nhanh.
    """,
    'author': "Sinh Viên A",
    'category': 'Operations/Logistics',
    'version': '18.0.1.0.0',
    'depends': ['base', 'mail', 'fleet', 'pizza_operation'],
    'data': [
        'views/delivery_menu.xml',
        'security/delivery_security.xml', 
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'wizard/assign_driver_wizard_views.xml',
        'views/delivery_order_views.xml',
        'views/delivery_driver_views.xml',
        'views/pizza_order_inherit_views.xml',
    ],
    'application': True,
    'license': 'LGPL-3',
}
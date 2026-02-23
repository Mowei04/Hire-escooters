from flask import Blueprint, jsonify, request
import sqlite3

admin_bp = Blueprint('admin', __name__)

# 获取数据库连接的辅助函数
def get_db_connection():
    conn = sqlite3.connect('scooter_mvp.db')
    conn.row_factory = sqlite3.Row
    return conn

### 1. 车辆状态维护
@admin_bp.route('/api/admin/scooters', methods=['GET'])
# @admin_required  # 此处后续对接成员A的权限校验
def list_scooters():
    """
    列出所有车辆及其状态
    """
    conn = get_db_connection()
    scooters = conn.execute('SELECT id, code, status, location_text FROM scooters').fetchall()
    conn.close()
    
    # 按照 api.md 要求的格式返回
    return jsonify({
        "items": [dict(row) for row in scooters]
    }), 200

### 2. 周收入汇总
@admin_bp.route('/api/admin/revenue/weekly', methods=['GET'])
# @admin_required  # 此处后续对接成员A的权限校验
def weekly_revenue():
    """
    周收入汇总接口
    """
    # 获取查询参数，如果没有则提供 api.md 中的默认值
    week_start = request.args.get('week_start', '2026-02-16')
    
    # 模拟逻辑：在实际应用中，你会根据 week_start 从 bookings 表计算总额
    # 这里严格遵守 api.md 定义的响应结构
    mock_data = {
        "week_start": week_start,
        "week_end": "2026-02-22",
        "total_revenue": "120.50",
        "by_plan": [
            {"plan_type": "1h", "revenue": "42.00"},
            {"plan_type": "4h", "revenue": "38.50"},
            {"plan_type": "1d", "revenue": "40.00"}
        ]
    }
    
    return jsonify(mock_data), 200
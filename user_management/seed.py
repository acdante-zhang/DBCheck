# -*- coding: utf-8 -*-
"""
种子数据初始化脚本
初始化默认管理员角色、管理员账户和菜单权限

运行方式:
  python -m user_management.seed
"""

import sys
import os

# 确保项目根目录在 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from user_management.models.db_manager import DBManager
from user_management.utils.password import hash_password


def init_seed_data():
    """初始化种子数据"""
    db = DBManager()
    print("开始初始化 RBAC 种子数据...")

    # 1. 创建默认角色
    roles_data = [
        ('admin', '系统管理员', '拥有所有权限'),
        ('viewer', '只读用户', '只能查看，不可修改'),
        ('operator', '运维人员', '可读写大部分功能'),
    ]
    for code, name, desc in roles_data:
        db.execute(
            """INSERT OR IGNORE INTO um_role(role_code, role_name, description)
               VALUES(?, ?, ?)""",
            (code, name, desc)
        )
    print("  ✅ 默认角色已创建: admin, viewer, operator")

    # 2. 给 admin 角色分配所有菜单的最高权限
    menus = db.query_all("SELECT id FROM um_menu")
    admin_role = db.query_one("SELECT id FROM um_role WHERE role_code='admin'")
    admin_perm = db.query_one("SELECT id FROM um_permission WHERE perm_level=4")

    if admin_role and admin_perm:
        for menu in menus:
            db.execute(
                """INSERT OR IGNORE INTO um_role_menu_perm(role_id, menu_id, perm_id)
                   VALUES(?, ?, ?)""",
                (admin_role['id'], menu['id'], admin_perm['id'])
            )
    print(f"  ✅ admin 角色已分配 {len(menus)} 个菜单的管理权限")

    # 3. 给 viewer 角色分配所有菜单的只读权限
    viewer_role = db.query_one("SELECT id FROM um_role WHERE role_code='viewer'")
    viewer_perm = db.query_one("SELECT id FROM um_permission WHERE perm_level=1")
    if viewer_role and viewer_perm:
        for menu in menus:
            db.execute(
                """INSERT OR IGNORE INTO um_role_menu_perm(role_id, menu_id, perm_id)
                   VALUES(?, ?, ?)""",
                (viewer_role['id'], menu['id'], viewer_perm['id'])
            )
    print(f"  ✅ viewer 角色已分配 {len(menus)} 个菜单的只读权限")

    # 4. 给 operator 角色分配所有菜单的读写权限
    operator_role = db.query_one("SELECT id FROM um_role WHERE role_code='operator'")
    operator_perm = db.query_one("SELECT id FROM um_permission WHERE perm_level=2")
    if operator_role and operator_perm:
        for menu in menus:
            db.execute(
                """INSERT OR IGNORE INTO um_role_menu_perm(role_id, menu_id, perm_id)
                   VALUES(?, ?, ?)""",
                (operator_role['id'], menu['id'], operator_perm['id'])
            )
    print(f"  ✅ operator 角色已分配 {len(menus)} 个菜单的读写权限")

    # 5. 创建默认管理员账户 admin / admin123
    pw_hash = hash_password('admin123')
    db.execute(
        """INSERT OR IGNORE INTO um_user(username, password, nickname)
           VALUES('admin', ?, '系统管理员')""",
        (pw_hash,)
    )
    print("  ✅ 默认管理员账户: admin / admin123")

    # 6. 绑定 admin 用户 → admin 角色
    admin_user = db.query_one("SELECT id FROM um_user WHERE username='admin'")
    if admin_user and admin_role:
        db.execute(
            """INSERT OR IGNORE INTO um_user_role(user_id, role_id)
               VALUES(?, ?)""",
            (admin_user['id'], admin_role['id'])
        )
    print("  ✅ admin 用户已绑定 admin 角色")

    # 7. 创建演示用户
    demo_users = [
        ('viewer', 'viewer123', '只读用户', 'viewer'),
        ('operator', 'operator123', '运维人员', 'operator'),
    ]
    for uname, upass, nick, role_code in demo_users:
        pw_hash = hash_password(upass)
        db.execute(
            """INSERT OR IGNORE INTO um_user(username, password, nickname)
               VALUES(?, ?, ?)""",
            (uname, pw_hash, nick)
        )
        user = db.query_one(f"SELECT id FROM um_user WHERE username='{uname}'")
        role = db.query_one(f"SELECT id FROM um_role WHERE role_code='{role_code}'")
        if user and role:
            db.execute(
                """INSERT OR IGNORE INTO um_user_role(user_id, role_id)
                   VALUES(?, ?)""",
                (user['id'], role['id'])
            )
    print("  ✅ 演示用户已创建:")
    print("     - viewer / viewer123 (只读用户)")
    print("     - operator / operator123 (运维人员)")

    # 8. 迁移：确保 health_monitor 菜单存在并分配权限
    hm_menu = db.query_one("SELECT id FROM um_menu WHERE menu_code='health_monitor'")
    if not hm_menu:
        max_order = db.query_one("SELECT MAX(sort_order) as m FROM um_menu")
        next_order = (max_order['m'] or 0) + 1
        db.execute(
            "INSERT OR IGNORE INTO um_menu(menu_code, menu_name, parent_id, sort_order) VALUES(?,?,?,?)",
            ('health_monitor', '健康监控', 0, next_order)
        )
        hm_menu = db.query_one("SELECT id FROM um_menu WHERE menu_code='health_monitor'")
        print("  ✅ 健康监控菜单已添加")
    # 为所有角色分配健康监控权限
    if hm_menu:
        roles = db.query_all("SELECT id, role_code FROM um_role")
        perm_map = {'admin': 4, 'operator': 2, 'viewer': 1}
        for role in roles:
            existing = db.query_one(
                "SELECT id FROM um_role_menu_perm WHERE role_id=? AND menu_id=?",
                (role['id'], hm_menu['id'])
            )
            if not existing:
                perm_level = perm_map.get(role['role_code'], 1)
                perm = db.query_one("SELECT id FROM um_permission WHERE perm_level=?", (perm_level,))
                if perm:
                    db.execute(
                        "INSERT OR IGNORE INTO um_role_menu_perm(role_id, menu_id, perm_id) VALUES(?,?,?)",
                        (role['id'], hm_menu['id'], perm['id'])
                    )
        print("  ✅ 健康监控权限已分配")

    print("\n🎉 RBAC 种子数据初始化完成!")


if __name__ == '__main__':
    init_seed_data()

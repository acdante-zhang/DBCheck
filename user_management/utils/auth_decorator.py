# -*- coding: utf-8 -*-
"""
权限校验装饰器 - JWT 认证 + Session fallback + RBAC 权限校验

认证优先级：
1. Authorization: Bearer <JWT>   → JWT 认证（兼容旧版 RBAC 独立登录）
2. Flask session                 → Session 认证（主应用统一登录）

Session 认证时：
- admin 角色直接拥有全部权限
- 其他角色从 um_user_role 关联查询权限
"""

from functools import wraps
from flask import request, g, jsonify, session
from user_management.utils.jwt_util import decode_token
from user_management.services.perm_service import PermService


def _resolve_user_from_session():
    """从 Flask session 解析用户信息，写入 g.current_user"""
    user_id = session.get('user_id')
    if not user_id:
        return False

    auth_source = session.get('auth_source', 'legacy')
    username = session.get('username', '')
    role = session.get('role', 'user')

    if auth_source == 'rbac':
        # RBAC 用户：尝试从 RBAC 数据库获取 roles 列表
        try:
            from user_management.services.user_service import UserService
            us = UserService()
            rbac_user = us.get_user(int(user_id))
            if rbac_user:
                roles = [r['role_code'] for r in rbac_user.get('roles', [])]
            else:
                roles = ['admin'] if role == 'admin' else ['user']
        except Exception:
            roles = ['admin'] if role == 'admin' else ['user']
    else:
        # legacy 用户：直接映射
        roles = ['admin'] if role == 'admin' else ['user']

    g.current_user = {
        'user_id': user_id,
        'username': username,
        'roles': roles,
        'auth_source': auth_source,
    }
    return True


def login_required(f):
    """验证用户是否登录（JWT Token → Session fallback）"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # 1. 尝试 JWT Bearer Token
        token = request.headers.get(
            'Authorization', ''
        ).replace('Bearer ', '')
        if token:
            try:
                payload = decode_token(token)
                g.current_user = payload
                return f(*args, **kwargs)
            except ValueError:
                # JWT 无效，继续尝试 session
                pass

        # 2. Fallback: Flask session
        if _resolve_user_from_session():
            return f(*args, **kwargs)

        # 3. 都失败
        return jsonify({
            'code': 401,
            'msg': '未登录，请先登录'
        }), 401
    return decorated


def require_permission(menu_code: str, min_level: int = 1):
    """
    验证当前用户对指定菜单的权限级别
    min_level: 1=只读, 2=读写, 3=修改, 4=管理

    Session 认证的 admin 用户直接放行
    """
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated(*args, **kwargs):
            user = g.current_user
            roles = user.get('roles', [])

            # Session admin → 直接放行
            if user.get('auth_source') == 'legacy' and 'admin' in roles:
                return f(*args, **kwargs)
            if user.get('auth_source') == 'rbac' and 'admin' in roles:
                return f(*args, **kwargs)

            # 其他情况：查询 RBAC 权限
            user_id = user['user_id']
            perm_service = PermService()
            actual_level = perm_service.get_user_menu_perm_level(
                user_id, menu_code
            )
            if actual_level < min_level:
                return jsonify({
                    'code': 403,
                    'msg': f'权限不足: 需要 {min_level} 级权限，当前 {actual_level} 级'
                }), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


def require_admin(f):
    """需要管理员权限（perm_level >= 4 on system_manage）"""
    @wraps(f)
    @require_permission('system_manage', min_level=4)
    def decorated(*args, **kwargs):
        return f(*args, **kwargs)
    return decorated


def asset_filter(f):
    """注入数据权限过滤：g.allowed_asset_ids"""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        user_id = g.current_user['user_id']
        perm_service = PermService()
        # admin 角色不过滤
        if 'admin' in g.current_user.get('roles', []):
            g.allowed_asset_ids = None  # None 表示不限制
        else:
            g.allowed_asset_ids = perm_service.get_allowed_asset_ids(user_id)
        return f(*args, **kwargs)
    return decorated

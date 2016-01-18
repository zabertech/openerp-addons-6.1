##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2016 Aki Mimoto (<http://www.zaber.com>)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.     
#
##############################################################################

import os
import datetime

from osv import fields, osv

class user_rpc_keys(osv.osv):
    _name = 'zerp.users.rpc.keys'
    _columns = {
        'name': fields.char('RPC Key',size=100,index=True,required=True),
        'user_id': fields.many2one('res.users', 'User',required=True),
        'expiry_time': fields.datetime('Key Expires'),
        'last_request': fields.datetime('Last Access Time'),
    }
    _defaults = {
        'name': lambda *a: os.urandom(16).encode('base-64')[:-3],
        'expiry_time': None,
    }
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'RPC Key must be unique!'),
    ]

    def allowed(self,cr,uid,ids):
        """ Returns a true value if the request is allowed
        """
        pass

    def create(self, cr, uid, vals, context=None):
        """ If someone tabs over in the view, it will mess up the date
            format. We'll just correct it here.
        """
        if vals.get('expiry_time') == '____-__-__ __:__:__':
            del vals['expiry_time']
        return super(user_rpc_keys,self).create(cr,uid,vals,context)


    def write(self, cr, uid, ids, vals, context=None):
        """ If someone tabs over in the view, it will mess up the date
            format. We'll just correct it here.
        """
        if vals.get('expiry_time') == '____-__-__ __:__:__':
            del vals['expiry_time']
        return super(user_rpc_keys,self).write(cr,uid,ids,vals,context)

    def login_api_key(self, cr, login, api_key):
        cr.execute('''
            SELECT    zurk.id,zurk.user_id
            FROM      zerp_users_rpc_keys zurk
            LEFT JOIN res_users ru
            ON        ru.id = zurk.user_id
            WHERE     ru.login = %s
                      AND zurk.name = %s
                      AND ( expiry_time > NOW() OR expiry_time IS NULL )
        ''',(login, api_key,))
        r = cr.fetchall()
        if r:
            r = r[0]
            cr.execute('''
              UPDATE    zerp_users_rpc_keys
              SET       last_request=now() AT TIME ZONE 'UTC'
              WHERE     id = %s
            ''',(r[0],))
            return r[1]
        return


    def check_api_key(self, cr, uid, api_key):
        # TODO: This can be cleaned up into a single UPDATE query
        cr.execute('''
            SELECT    id,user_id
            FROM      zerp_users_rpc_keys
            WHERE     user_id = %s
                      AND name = %s
                      AND ( expiry_time > NOW() OR expiry_time IS NULL )
        ''',(uid, api_key,))
        r = cr.fetchall()
        if r:
            r = r[0]
            cr.execute('''
              UPDATE    zerp_users_rpc_keys
              SET       last_request=now() AT TIME ZONE 'UTC'
              WHERE     id = %s
            ''',(r[0],))
            return r[1]
        return

class user_sessions(osv.osv_memory):
    _name = 'zerp.users.sessions'
    _columns = {
        'name': fields.char('Session Key',size=100,index=True,required=True),
        'user_id': fields.many2one('res.users','User',required=True),
        'last_request': fields.datetime('Last Access Time'),
    }
    _defaults = {
        'name': lambda *a: os.urandom(16).encode('base-64')[:-3],
        'last_request': lambda *a: datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
    }
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'RPC Key must be unique!'),
    ]

    def create_session(self,cr,uid,target_uid=None):
        """ Creates a new session for the user provided they are allowed to
            create sessions
        """
        if target_uid is None:
            target_uid = uid

        # If the uid and the target_uid is the same, the user is creating their
        # own session which is okay to create via admin. Otherwise we'll rely
        # on the security mechanism of the system to allow create access
        if uid != target_uid:
            uid = 1

        session_id = self.create(cr,uid,{'user_id':target_uid})
        session = self.browse(cr,1,session_id)
        key_new = session.name

        return key_new

    def check(self,cr,uid,session_key):
        """ Checks to see if the session exists
        """
        sess_ids = self.search(cr,1,[('name','=',session_key)])
        if not sess_ids: return
        sess = self.search(cr,1,sess_ids[0])
        if uid != sess.user_id.id: return
        return True

    def touch(self,cr,session_key):
        """ Based upon the session key, updates the last seen
            timestamp on a session record
        """
        sess_ids = self.search(cr,1,[('name','=',session_key)])
        if not sess_ids: return
        last_request = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        return self.write(cr,1,sess_ids,{'last_request':last_request})

    def session_timeout(self):
        # FIXME: Staleness setting needs to be customizable
        session_timeout = 30*60
        return session_timeout

    def flush_stale(self,cr):
        cr.execute('''
            DELETE FROM     zerp_users_sessions
            WHERE
                            age(now() at TIME ZONE 'UTC',create_date) > interval %s
        ''',('{} seconds'.format(self.session_timeout()),))

    def login_session_id(self, cr, login, api_key):
        # TODO: This can be cleaned up into a single UPDATE query
        cr.execute('''
            SELECT    zus.id,zus.user_id
            FROM      zerp_users_sessions zus
            LEFT JOIN res_users ru
            ON        ru.id = zus.user_id
            WHERE     ru.login = %s
                      AND zus.name = %s
        ''',(login,api_key,))
        r = cr.fetchall()
        if r:
            r = r[0]
            cr.execute('''
              UPDATE    zerp_users_sessions
              SET       last_request=now() AT TIME ZONE 'UTC'
              WHERE     id = %s
            ''',(r[0],))
            return r[1]
        return

    def check_session_id(self, cr, uid, api_key):
        # TODO: This can be cleaned up into a single UPDATE query
        cr.execute('''
            SELECT    id,user_id
            FROM      zerp_users_sessions
            WHERE     user_id = %s
                      AND name = %s
        ''',(uid,api_key,))
        r = cr.fetchall()
        if r:
            r = r[0]
            cr.execute('''
              UPDATE    zerp_users_sessions
              SET       last_request=now() AT TIME ZONE 'UTC'
              WHERE     id = %s
            ''',(r[0],))
            return r[1]
        return


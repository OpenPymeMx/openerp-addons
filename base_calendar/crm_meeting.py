#  -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-today OpenERP SA (<http://www.openerp.com>)
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

import time

from openerp.osv import fields, osv
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT
from openerp.tools.translate import _
from base_calendar import get_real_ids, base_calendar_id2real_id
from datetime import datetime, timedelta, date
import pytz
from openerp import tools, SUPERUSER_ID
import openerp
import hashlib

import ipdb;

#
# crm.meeting is defined here so that it may be used by modules other than crm,
# without forcing the installation of crm.
#

class crm_meeting_type(osv.Model):
    _name = 'crm.meeting.type'
    _description = 'Meeting Type'
    _columns = {
        'name': fields.char('Name', size=64, required=True, translate=True),
    }

class crm_meeting(osv.Model):
    """ Model for CRM meetings """
    _name = 'crm.meeting'
    _description = "Meeting"
    _order = "id desc"
    _inherit = ["mail.thread", "ir.needaction_mixin"]
    
    def _get_recurrence_end_date(self, cr, uid, ids, name, arg, context=None):
        """Get a good estimate of the end of the timespan concerned by an event.

        This means we need to concider the last event of a recurrency, and that we
        add its duration. For simple events (no rrule), the date_deadline is sufficient.

        This value is stored in database and will help select events that should be
        concidered candidate for display when filters are made upon dates (typically
        the agenda filter will make one-month, one-week, one-day timespan searches).

        """

        if not context:
            context = {}
            
        events = self.read(cr, uid, ids, ['rrule', 'exdate', 'exrule', 'duration', 'date_deadline', 'date', 'vtimezone'], context=context)
        result = {}
        for event in events:

            duration = timedelta(hours=event['duration'])

            if event['rrule']:
                all_dates = get_recurrent_dates(
                    event['rrule'], event['date'], event['exdate'], event['vtimezone'],
                    event['exrule'], context=context)
                if not event['vtimezone'] and not context.get('tz'):
                    ## We are called by the server probably at update time (no
                    ## context), and no vtimezone was recorded, so we have no
                    ## idea of possible client timezone so we have a possible
                    ## one-day-of error when applying RRULEs on floating dates.
                    ## Let's add a day.
                    duration += timedelta(days=1)
                result[event['id']] = (all_dates[-1] + duration).astimezone(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S") \
                    if all_dates else None
            else:
                result[event['id']] = event['date_deadline']

        return result
   
    def _find_user_attendee(self, cr, uid, meeting_ids, context=None):
        attendee_pool = self.pool.get('calendar.attendee')
        user = self.pool.get('res.users').browse(cr, uid, uid, context=context)
        for meeting_id in meeting_ids:
            for attendee in self.browse(cr,uid,meeting_id,context).attendee_ids:
                if user.partner_id.id == attendee.partner_id.id:
                    return attendee
        return False
    
    def _compute_time(self, cr, uid, meeting_id, context=None):
        """
            Return date and time (from to from) based on duration with timezone in string :
            eg.
            1) if user add duration for 2 hours, return : August-23-2013 at ( 04-30 To 06-30) (Europe/Brussels)
            2) if event all day ,return : AllDay, July-31-2013
        """
        if context is None:
            context = {}
        tz = context.get('tz', pytz.timezone('UTC'))
        meeting = self.browse(cr, uid, meeting_id, context=context)
        date = fields.datetime.context_timestamp(cr, uid, datetime.strptime(meeting.date, tools.DEFAULT_SERVER_DATETIME_FORMAT), context=context)
        date_deadline = fields.datetime.context_timestamp(cr, uid, datetime.strptime(meeting.date_deadline, tools.DEFAULT_SERVER_DATETIME_FORMAT), context=context)
        event_date = date.strftime('%B-%d-%Y')
        event_time = date.strftime('%H-%M')
        if meeting.allday:
            time =  _("AllDay , %s") % (event_date)
        elif meeting.duration < 24:
            duration =  date + timedelta(hours= meeting.duration)
            time = ("%s at ( %s To %s) (%s)") % (event_date, event_time, duration.strftime('%H-%M'), tz)
        else :
            time = ("%s at %s To\n %s at %s (%s)") % (event_date, event_time, date_deadline.strftime('%B-%d-%Y'), date_deadline.strftime('%H-%M'), tz)
        return time
    
    def _compute(self, cr, uid, ids, fields, arg, context=None):
        res = {}
        for meeting_id in ids:
            res[meeting_id] = {}
            attendee = self._find_user_attendee(cr, uid, [meeting_id], context)
            for field in fields:
                if field == 'is_attendee':
                    res[meeting_id][field] = True if attendee else False
                elif field == 'attendee_status':
                    res[meeting_id][field] = attendee.state if attendee else 'needs-action'
                elif field == 'event_time':
                    res[meeting_id][field] = self._compute_time(cr, uid, meeting_id, context=context)
        return res
      
    def _get_rulestring(self, cr, uid, ids, name, arg, context=None):
        """
        Gets Recurrence rule string according to value type RECUR of iCalendar from the values given.
        @return: dictionary of rrule value.
        """

        result = {}
        if not isinstance(ids, list):
            ids = [ids]

        for id in ids:
            #read these fields as SUPERUSER because if the record is private a normal search could return False and raise an error
            data = self.browse(cr, SUPERUSER_ID, id, context=context)
            if data.interval < 0:
                raise osv.except_osv(_('Warning!'), _('Interval cannot be negative.'))
            if data.count <= 0:
                raise osv.except_osv(_('Warning!'), _('Count cannot be negative or 0.'))
            data = self.browse(cr, uid, id, context=context)
                        
            if data.recurrency:
                result[data.id] = self.compute_rule_string(data)
            else:
                result[data.id] = ""
        return result

    def _rrule_write(self, obj, cr, uid, ids, field_name, field_value, args, context=None):
        data = self._get_empty_rrule_data()
        if field_value:
            data['recurrency'] = True
            for event in self.browse(cr, uid, ids, context=context):
                rdate = rule_date or event.date
                update_data = self._parse_rrule(field_value, dict(data), rdate)
                data.update(update_data)
                self.write(cr, uid, ids, data, context=context)
        return True

    def _tz_get(self, cr, uid, context=None):
        return [(x.lower(), x) for x in pytz.all_timezones]

    _columns = {
        'create_date': fields.datetime('Creation Date', readonly=True),
        'write_date': fields.datetime('Write Date', readonly=True),
        'date_open': fields.datetime('Confirmed', readonly=True),
        'date_closed': fields.datetime('Closed', readonly=True),
        'state': fields.selection([('draft', 'Unconfirmed'), ('open', 'Confirmed')], string='Status', size=16, readonly=True, track_visibility='onchange'),
        # Meeting fields
        'name': fields.char('Meeting Subject', size=128, required=True, states={'done': [('readonly', True)]}),
        'is_attendee': fields.function(_compute, string='Attendee', type="boolean", multi='attendee'),
        'attendee_status': fields.function(_compute, string='Attendee Status', type="selection", multi='attendee'),
        'event_time': fields.function(_compute, string='Event Time', type="char", multi='attendee'),
        
        # ---------------------
        # OLD CALENDAR_EVENT 
        # ---------------------
        'id': fields.integer('ID', readonly=True),
        'sequence': fields.integer('Sequence'),
        
        'date': fields.datetime('Date', states={'done': [('readonly', True)]}, required=True,),
        'date_deadline': fields.datetime('End Date', states={'done': [('readonly', True)]}, required=True,),
        
        'duration': fields.float('Duration', states={'done': [('readonly', True)]}),
        'description': fields.text('Description', states={'done': [('readonly', True)]}),
        'class': fields.selection([('public', 'Public'), ('private', 'Private'), ('confidential', 'Public for Employees')], 'Privacy', states={'done': [('readonly', True)]}),
        'location': fields.char('Location', size=264, help="Location of Event", states={'done': [('readonly', True)]}),
        'show_as': fields.selection([('free', 'Free'), ('busy', 'Busy')], 'Show Time as', states={'done': [('readonly', True)]}),        
        'state': fields.selection([('tentative', 'Uncertain'),('cancelled', 'Cancelled'),('confirmed', 'Confirmed'),],'Status', readonly=True),
        
        
        #FIELD FOR RECURRENCY
        'exdate': fields.text('Exception Date/Times', help="This property defines the list of date/time exceptions for a recurring calendar component."),
        'exrule': fields.char('Exception Rule', size=352, help="Defines a rule or repeating pattern of time to exclude from the recurring rule."),
        'rrule': fields.function(_get_rulestring, type='char', size=124, fnct_inv=_rrule_write, store=True, string='Recurrent Rule'),
        'rrule_type': fields.selection([('daily', 'Day(s)'),('weekly', 'Week(s)'),('monthly', 'Month(s)'),('yearly', 'Year(s)')], 'Recurrency', states={'done': [('readonly', True)]}, help="Let the event automatically repeat at that interval"),
        'recurrency': fields.boolean('Recurrent', help="Recurrent Meeting"),
        'recurrent_id': fields.integer('Recurrent ID'),
        'recurrent_id_date': fields.datetime('Recurrent ID date'),
        'recurrence_end_date': fields.function(_get_recurrence_end_date, type='datetime', store=True, string='Recurrence end date',priority=30),
        'vtimezone': fields.selection(_tz_get, size=64, string='Timezone'),
        'end_type' : fields.selection([('count', 'Number of repetitions'), ('end_date','End date')], 'Recurrence Termination'),
        'interval': fields.integer('Repeat Every', help="Repeat every (Days/Week/Month/Year)"),
        'count': fields.integer('Repeat', help="Repeat x times"),
        'mo': fields.boolean('Mon'),
        'tu': fields.boolean('Tue'),
        'we': fields.boolean('Wed'),
        'th': fields.boolean('Thu'),
        'fr': fields.boolean('Fri'),
        'sa': fields.boolean('Sat'),
        'su': fields.boolean('Sun'),
        'select1': fields.selection([('date', 'Date of month'),('day', 'Day of month')], 'Option'),
        'day': fields.integer('Date of month'),
        'week_list': fields.selection([('MO', 'Monday'),('TU', 'Tuesday'),('WE', 'Wednesday'),('TH', 'Thursday'),('FR', 'Friday'),('SA', 'Saturday'),('SU', 'Sunday')], 'Weekday'),
        'byday': fields.selection([('1', 'First'),('2', 'Second'),('3', 'Third'),('4', 'Fourth'),('5', 'Fifth'),('-1', 'Last')], 'By day'),
        'end_date': fields.date('Repeat Until'),
        
        'user_id': fields.many2one('res.users', 'Responsible', states={'done': [('readonly', True)]}),
                
        'allday': fields.boolean('All Day', states={'done': [('readonly', True)]}),
        'active': fields.boolean('Active', help="If the active field is set to true, it will allow you to hide the event alarm information without removing it."),

        'categ_ids': fields.many2many('crm.meeting.type', 'meeting_category_rel', 'event_id', 'type_id', 'Tags'),
        
        'attendee_ids': fields.many2many('calendar.attendee', 'crmmeeting_attendee_rel', 'crmmeeting_id', 'attendee_id', 'Attendees'),
        'partner_ids': fields.many2many('res.partner', string='Attendees', states={'done': [('readonly', True)]}),
        
        'alarm_ids': fields.many2many('calendar.alarm', string='Reminders'),
    }
    _defaults = {
        'state': 'open',
        'end_type': 'count',
        'count': 1,
        'rrule_type': False,
        'state': 'tentative',
        'class': 'public',
        'show_as': 'busy',
        'select1': 'date',
        'interval': 1,
        'active': 1,
        'user_id': lambda self, cr, uid, ctx: uid
    }
        
    def _check_closing_date(self, cr, uid, ids, context=None):
        for event in self.browse(cr, uid, ids, context=context):
            if event.date_deadline < event.date:
                return False
        return True
    
    _constraints = [
        (_check_closing_date, 'Error ! End date cannot be set before start date.', ['date_deadline']),
    ]
    
    def onchange_dates(self, cr, uid, ids, start_date, duration=False, end_date=False, allday=False, context=None):
        """Returns duration and/or end date based on values passed
        @param ids: List of calendar event's IDs.
        @param start_date: Starting date
        @param duration: Duration between start date and end date
        @param end_date: Ending Datee
        """
        if context is None:
            context = {}

        value = {}
        if not start_date:
            return value
        if not end_date and not duration:
            duration = 1.00
            value['duration'] = duration

        start = datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S")
        if allday: # For all day event
            duration = 24.0
            value['duration'] = duration
            # change start_date's time to 00:00:00 in the user's timezone
            user = self.pool.get('res.users').browse(cr, uid, uid)
            tz = pytz.timezone(user.tz) if user.tz else pytz.utc
            start = pytz.utc.localize(start).astimezone(tz)     # convert start in user's timezone
            start = start.replace(hour=0, minute=0, second=0)   # change start's time to 00:00:00
            start = start.astimezone(pytz.utc)                  # convert start back to utc
            start_date = start.strftime("%Y-%m-%d %H:%M:%S")
            value['date'] = start_date

        if end_date and not duration:
            end = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S")
            diff = end - start
            duration = float(diff.days)* 24 + (float(diff.seconds) / 3600)
            value['duration'] = round(duration, 2)
        elif not end_date:
            end = start + timedelta(hours=duration)
            value['date_deadline'] = end.strftime("%Y-%m-%d %H:%M:%S")
        elif end_date and duration and not allday:
            # we have both, keep them synchronized:
            # set duration based on end_date (arbitrary decision: this avoid
            # getting dates like 06:31:48 instead of 06:32:00)
            end = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S")
            diff = end - start
            duration = float(diff.days)* 24 + (float(diff.seconds) / 3600)
            value['duration'] = round(duration, 2)

        return {'value': value}

    def unlink_events(self, cr, uid, ids, context=None):
        """
        This function deletes event which are linked with the event with recurrent_id
                (Removes the events which refers to the same UID value)
        """
        if context is None:
            context = {}
        for event_id in ids:
            cr.execute("select id from %s where recurrent_id=%%s" % (self._table), (event_id,))
            r_ids = map(lambda x: x[0], cr.fetchall())
            self.unlink(cr, uid, r_ids, context=context)
        return True

    def new_invitation_token(self, cr, uid, record, partner_id):
        db_uuid = self.pool.get('ir.config_parameter').get_param(cr, uid, 'database.uuid')
        invitation_token = hashlib.sha256('%s-%s-%s-%s-%s' % (time.time(), db_uuid, record._name, record.id, partner_id)).hexdigest()
        return invitation_token
        
    def create_attendees(self, cr, uid, ids, context):
        att_obj = self.pool.get('calendar.attendee')
        user_obj = self.pool.get('res.users')
        current_user = user_obj.browse(cr, uid, uid, context=context)
        for event in self.browse(cr, uid, ids, context):
            attendees = {}
            for att in event.attendee_ids:
                attendees[att.partner_id.id] = True
            new_attendees = []
            mail_to = ""
            for partner in event.partner_ids:
                if partner.id in attendees:
                    continue
                access_token = self.new_invitation_token(cr, uid, event, partner.id)
                att_id = self.pool.get('calendar.attendee').create(cr, uid, {
                    'partner_id': partner.id,
                    'user_id': partner.user_ids and partner.user_ids[0].id or False,
                    'ref': event.id,
                    'access_token': access_token,
                    'email': partner.email,
                }, context=context)
                if partner.email:
                    mail_to = mail_to + " " + partner.email
                self.write(cr, uid, [event.id], {
                    'attendee_ids': [(4, att_id)]
                }, context=context)
                new_attendees.append(att_id)
            if mail_to and current_user.email:
                is_sent_mail = att_obj._send_mail(cr, uid, new_attendees, mail_to,
                    email_from = current_user.email, context=context)
                if is_sent_mail:
                    self.message_post(cr, uid, event.id, body=_("An invitation email has been sent to attendee(s)"), context=context)
        return True

    def get_recurrent_ids(self, cr, uid, select, domain, limit=100, context=None):
        """Gives virtual event ids for recurring events based on value of Recurrence Rule
        This method gives ids of dates that comes between start date and end date of calendar views
      
        @param limit: The Number of Results to Return """
        if not context:
            context = {}

        result = []
#         for data in self.read(cr, uid, select, ['rrule', 'recurrency', 'exdate', 'exrule', 'date'], context=context):
        for data in self.read(cr, uid, select, ['rrule', 'recurrency', 'exdate', 'exrule', 'date', 'vtimezone'], context=context):
            if not data['recurrency'] or not data['rrule']:
                result.append(data['id'])
                continue
#             event_date = datetime.strptime(data['date'], "%Y-%m-%d %H:%M:%S")
#             event_date = pytz.UTC.localize(event_date)
            # TOCHECK: the start date should be replaced by event date; the event date will be changed by that of calendar code

#             if not data['rrule']:
#                 continue
# 
#             exdate = data['exdate'] and data['exdate'].split(',') or []
#             rrule_str = data['rrule']
#             new_rrule_str = []
#             rrule_until_date = False
#             is_until = False
#             for rule in rrule_str.split(';'):
#                 name, value = rule.split('=')
#                 if name == "UNTIL":
#                     is_until = True
#                     value = parser.parse(value)
#                     rrule_until_date = parser.parse(value.strftime("%Y-%m-%d %H:%M:%S"))
#                     value = value.strftime("%Y%m%d%H%M%S")
#                 new_rule = '%s=%s' % (name, value)
#                 new_rrule_str.append(new_rule)
#             new_rrule_str = ';'.join(new_rrule_str)
#             rdates = get_recurrent_dates(str(new_rrule_str), exdate, event_date, data['exrule'])
#             rdates = get_recurrent_dates(data['rrule'], exdate, event_date, data['exrule'])
            rdates = get_recurrent_dates(data['rrule'], data['date'], data['exdate'], data['vtimezone'], data['exrule'], context=context)
            for r_date in rdates:
                # fix domain evaluation
                # step 1: check date and replace expression by True or False, replace other expressions by True
                # step 2: evaluation of & and |
                # check if there are one False
                pile = []
                ok = True
                for arg in domain:
                    if str(arg[0]) in (str('date'), str('date_deadline')):
                        if (arg[1] == '='):
                            ok = r_date.strftime('%Y-%m-%d')==arg[2]
                        if (arg[1] == '>'):
                            ok = r_date.strftime('%Y-%m-%d')>arg[2]
                        if (arg[1] == '<'):
                            ok = r_date.strftime('%Y-%m-%d')<arg[2]
                        if (arg[1] == '>='):
                            ok = r_date.strftime('%Y-%m-%d')>=arg[2]
                        if (arg[1] == '<='):
                            ok = r_date.strftime('%Y-%m-%d')<=arg[2]
                        pile.append(ok)
                    elif str(arg) == str('&') or str(arg) == str('|'):
                        pile.append(arg)
                    else:
                        pile.append(True)
                pile.reverse()
                new_pile = []
                for item in pile:
                    if not isinstance(item, basestring):
                        res = item
                    elif str(item) == str('&'):
                        first = new_pile.pop()
                        second = new_pile.pop()
                        res = first and second
                    elif str(item) == str('|'):
                        first = new_pile.pop()
                        second = new_pile.pop()
                        res = first or second
                    new_pile.append(res)

                if [True for item in new_pile if not item]:
                    continue
                idval = real_id2base_calendar_id(data['id'], r_date.strftime("%Y-%m-%d %H:%M:%S"))
                result.append(idval)

        if isinstance(select, (str, int, long)):
            return ids and ids[0] or False
        else:
            ids = list(set(result))
        return ids

    def compute_rule_string(self, data):
        """
        Compute rule string according to value type RECUR of iCalendar from the values given.
        @param self: the object pointer
        @param data: dictionary of freq and interval value
        @return: string containing recurring rule (empty if no rule)
        """
        def get_week_string(freq, data):
            weekdays = ['mo', 'tu', 'we', 'th', 'fr', 'sa', 'su']
            if freq == 'weekly':
                byday = map(lambda x: x.upper(), filter(lambda x: data.get(x) and x in weekdays, data))
                if byday:
                    return ';BYDAY=' + ','.join(byday)
            return ''

        def get_month_string(freq, data):
            if freq == 'monthly':
                if data.get('select1')=='date' and (data.get('day') < 1 or data.get('day') > 31):
                    raise osv.except_osv(_('Error!'), ("Please select a proper day of the month."))

                if data.get('select1')=='day':
                    return ';BYDAY=' + data.get('byday') + data.get('week_list')
                elif data.get('select1')=='date':
                    return ';BYMONTHDAY=' + str(data.get('day'))
            return ''

        def get_end_date(data):
            if data.get('end_date'):
                data['end_date_new'] = ''.join((re.compile('\d')).findall(data.get('end_date'))) + 'T235959Z'

            return (data.get('end_type') == 'count' and (';COUNT=' + str(data.get('count'))) or '') +\
                             ((data.get('end_date_new') and data.get('end_type') == 'end_date' and (';UNTIL=' + data.get('end_date_new'))) or '')

        freq = data.get('rrule_type', False)
        res = ''
        if freq:
            interval_srting = data.get('interval') and (';INTERVAL=' + str(data.get('interval'))) or ''
            res = 'FREQ=' + freq.upper() + get_week_string(freq, data) + interval_srting + get_end_date(data) + get_month_string(freq, data)

        return res

    def _get_empty_rrule_data(self):
        return  {
            'byday' : False,
            'recurrency' : False,
            'end_date' : False,
            'rrule_type' : False,
            'select1' : False,
            'interval' : 0,
            'count' : False,
            'end_type' : False,
            'mo' : False,
            'tu' : False,
            'we' : False,
            'th' : False,
            'fr' : False,
            'sa' : False,
            'su' : False,
            'exrule' : False,
            'day' : False,
            'week_list' : False
        }

    def _parse_rrule(self, rule, data, date_start):
        day_list = ['mo', 'tu', 'we', 'th', 'fr', 'sa', 'su']
        rrule_type = ['yearly', 'monthly', 'weekly', 'daily']
        r = rrule.rrulestr(rule, dtstart=datetime.strptime(date_start, "%Y-%m-%d %H:%M:%S"))

        if r._freq > 0 and r._freq < 4: 
            data['rrule_type'] = rrule_type[r._freq]

        data['count'] = r._count
        data['interval'] = r._interval
        data['end_date'] = r._until and r._until.strftime("%Y-%m-%d %H:%M:%S")
        #repeat weekly
        if r._byweekday:
            for i in xrange(0,7):
                if i in r._byweekday:
                    data[day_list[i]] = True
            data['rrule_type'] = 'weekly'
        #repeat monthly by nweekday ((weekday, weeknumber), )
        if r._bynweekday:
            data['week_list'] = day_list[r._bynweekday[0][0]].upper()
            data['byday'] = r._bynweekday[0][1]
            data['select1'] = 'day'
            data['rrule_type'] = 'monthly'

        if r._bymonthday:
            data['day'] = r._bymonthday[0]
            data['select1'] = 'date'
            data['rrule_type'] = 'monthly'

        #repeat yearly but for openerp it's monthly, take same information as monthly but interval is 12 times
        if r._bymonth:
            data['interval'] = data['interval'] * 12

        #FIXEME handle forever case
        #end of recurrence
        #in case of repeat for ever that we do not support right now
        if not (data.get('count') or data.get('end_date')):
            data['count'] = 100
        if data.get('count'):
            data['end_type'] = 'count'
        else:
            data['end_type'] = 'end_date'
        return data

    def _get_data(self, cr, uid, id, context=None):
        return self.read(cr, uid, id,['date', 'date_deadline'])

    def need_to_update(self, event_id, vals):
        split_id = str(event_id).split("-")
        if len(split_id) < 2:
            return False
        else:
            date_start = vals.get('date', '')
            try:
                date_start = datetime.strptime(date_start, '%Y-%m-%d %H:%M:%S').strftime("%Y%m%d%H%M%S")
                return date_start == split_id[1]
            except Exception:
                return True
    
    def message_get_subscription_data(self, cr, uid, ids, user_pid=None, context=None):
        res = {}
        for virtual_id in ids:
            real_id = base_calendar_id2real_id(virtual_id)
            result = super(crm_meeting, self).message_get_subscription_data(cr, uid, [real_id], user_pid=None, context=context)
            res[virtual_id] = result[real_id]
        return res
        
    def onchange_partner_ids(self, cr, uid, ids, value, context=None):
        """ The basic purpose of this method is to check that destination partners
            effectively have email addresses. Otherwise a warning is thrown.
            :param value: value format: [[6, 0, [3, 4]]]
        """
        res = {'value': {}}
        if not value or not value[0] or not value[0][0] == 6:
            return
        res.update(self.check_partners_email(cr, uid, value[0][2], context=context))
        return res

    def check_partners_email(self, cr, uid, partner_ids, context=None):
        ##TODO : REFACTOR !
        """ Verify that selected partner_ids have an email_address defined.
            Otherwise throw a warning. """
        partner_wo_email_lst = []
        for partner in self.pool.get('res.partner').browse(cr, uid, partner_ids, context=context):
            if not partner.email:
                partner_wo_email_lst.append(partner)
        if not partner_wo_email_lst:
            return {}
        warning_msg = _('The following contacts have no email address :')
        for partner in partner_wo_email_lst:
            warning_msg += '\n- %s' % (partner.name)
        return {'warning': {
                    'title': _('Email addresses not found'),
                    'message': warning_msg,
                    }
                }
    # ----------------------------------------
    # OpenChatter
    # ----------------------------------------

    # shows events of the day for this user
   
    def _needaction_domain_get(self, cr, uid, context=None):
        return [('date', '<=', time.strftime(DEFAULT_SERVER_DATE_FORMAT + ' 23:59:59')), ('date_deadline', '>=', time.strftime(DEFAULT_SERVER_DATE_FORMAT + ' 23:59:59')), ('user_id', '=', uid)]

    def message_post(self, cr, uid, thread_id, body='', subject=None, type='notification',
                        subtype=None, parent_id=False, attachments=None, context=None, **kwargs):
        if isinstance(thread_id, str):
            thread_id = get_real_ids(thread_id)
        if context.get('default_date'):
            del context['default_date']
        return super(crm_meeting, self).message_post(cr, uid, thread_id, body=body, subject=subject, type=type, subtype=subtype, parent_id=parent_id, attachments=attachments, context=context, **kwargs)

    def do_decline(self, cr, uid, ids, context=None):
         attendee_pool = self.pool.get('calendar.attendee')
         attendee = self._find_user_attendee(cr, uid, ids, context)
         return attendee_pool.do_decline(cr, uid, [attendee.id], context=context)

    def do_accept(self, cr, uid, ids, context=None):
        attendee_pool = self.pool.get('calendar.attendee')
        attendee = self._find_user_attendee(cr, uid, ids, context)
        return attendee_pool.do_accept(cr, uid, [attendee.id], context=context)

    def get_attendee(self, cr, uid, meeting_id, context=None):
        invitation = {'meeting':{}, 'attendee': [], 'logo': ''}
        attendee_pool = self.pool.get('calendar.attendee')
        company_logo = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.logo
        meeting = self.browse(cr, uid, int(meeting_id), context)
        invitation['meeting'] = {
                'event':meeting.name,
                'organizer': meeting.organizer,
                'where': meeting.location,
                'when':meeting.event_time
        }
        invitation['logo'] = company_logo.replace('\n','\\n') if company_logo else ''
        for attendee in meeting.attendee_ids:
            invitation['attendee'].append({'name':attendee.cn,'status': attendee.state})
        return invitation

    def get_interval(self, cr, uid, ids, date, interval, context=None):
        date = datetime.strptime(date, DEFAULT_SERVER_DATETIME_FORMAT)
        if interval == 'day':
            res = str(date.day)
        elif interval == 'month':
            res = date.strftime('%B') + " " + str(date.year)
        elif interval == 'dayname':
            res = date.strftime('%A')
        elif interval == 'time':
            res = date.strftime('%I:%M %p')
        return res
    
    def _set_recurrency_end_date(self, data, context=None):
        end_date = data.get('end_date')
        if data.get('recurrency') and data.get('end_type') in ('count', unicode('count')):
            data_date_deadline = datetime.strptime(data.get('date_deadline'), '%Y-%m-%d %H:%M:%S')
            if data.get('rrule_type') in ('daily', unicode('count')):
                rel_date = relativedelta(days=data.get('count')+1)
            elif data.get('rrule_type') in ('weekly', unicode('weekly')):
                rel_date = relativedelta(days=(data.get('count')+1)*7)
            elif data.get('rrule_type') in ('monthly', unicode('monthly')):
                rel_date = relativedelta(months=data.get('count')+1)
            elif data.get('rrule_type') in ('yearly', unicode('yearly')):
                rel_date = relativedelta(years=data.get('count')+1)
            end_date = data_date_deadline + rel_date
        return end_date

    def search(self, cr, uid, args, offset=0, limit=0, order=None, context=None, count=False):
        print 'IN SEARCH',args
        
        if context is None:
            context={}        
    
        if context.get('mymeetings',False):
            partner_id = self.pool.get('res.users').browse(cr, uid, uid, context).partner_id.id
            args += ['|', ('partner_ids', 'in', [partner_id]), ('user_id', '=', uid)]
        
        
        new_args = []    
        for arg in args:
            new_arg = arg
            if arg[0] in ('date_deadline', unicode('date_deadline')):
                if context.get('virtual_id', True):
#                     new_args += ['|','&',('recurrency','=',1),('end_date', arg[1], arg[2])]
                    new_args += ['|','&',('recurrency','=',1),('recurrence_end_date', arg[1], arg[2])]
            elif arg[0] == "id":
                new_id = get_real_ids(arg[2])
                new_arg = (arg[0], arg[1], new_id)
            new_args.append(new_arg)
        #offset, limit and count must be treated separately as we may need to deal with virtual ids
        
        res = super(crm_meeting,self).search(cr, uid, new_args, offset=0, limit=0, order=order, context=context, count=False)
        
        if context.get('virtual_id', True):
            res = self.get_recurrent_ids(cr, uid, res, args, limit, context=context)
        if count:
            return len(res)
        elif limit:
            return res[offset:offset+limit]
        return res

    def copy(self, cr, uid, id, default=None, context=None):
        if context is None:
            context = {}
            
        default = default or {}
        default['attendee_ids'] = False
        
        res = super(crm_meeting, self).copy(cr, uid, base_calendar_id2real_id(id), default, context)
        #alarm_obj = self.pool.get('res.alarm')
        #alarm_obj.do_alarm_create(cr, uid, [res], self._name, 'date', context=context)
        return res        

    def write(self, cr, uid, ids, values, context=None):
        """ Override to add case management: open/close dates """
                
        def _only_changes_to_apply_on_real_ids(field_names):
            ''' return True if changes are only to be made on the real ids'''
            for field in field_names:
                if field not in ['message_follower_ids']:
                    return False
            return True
        
        context = context or {}
        if isinstance(ids, (str, int, long)):
            ids = [ids]
        res = False
                
        if values.get('state')and values.get('state') == 'open':
            values['date_open'] = fields.datetime.now()
            
         # Special write of complex IDS
        for event_id in ids[:]:
            if len(str(event_id).split('-')) == 1:
                continue
            ids.remove(event_id)
            real_event_id = base_calendar_id2real_id(event_id)

            # if we are setting the recurrency flag to False or if we are only changing fields that
            # should be only updated on the real ID and not on the virtual (like message_follower_ids):
            # then set real ids to be updated.
            if not vals.get('recurrency', True) or _only_changes_to_apply_on_real_ids(vals.keys()):
                ids.append(real_event_id)
                continue

            #if edit one instance of a reccurrent id
            data = self.read(cr, uid, event_id, ['date', 'date_deadline', \
                                                'rrule', 'duration', 'exdate'])
            if data.get('rrule'):
                data.update(
                    vals,
                    recurrent_id=real_event_id,
                    recurrent_id_date=data.get('date'),
                    rrule_type=False,
                    rrule='',
                    recurrency=False,
                )
                #do not copy the id
                if data.get('id'):
                    del(data['id'])
                new_id = self.copy(cr, uid, real_event_id, default=data, context=context)

                date_new = event_id.split('-')[1]
                date_new = time.strftime("%Y%m%dT%H%M%SZ", \
                             time.strptime(date_new, "%Y%m%d%H%M%S"))
                exdate = (data['exdate'] and (data['exdate'] + ',')  or '') + date_new
                res = super(crm_meeting, self).write(cr, uid, [real_event_id], {'exdate': exdate})

                context.update({'active_id': new_id, 'active_ids': [new_id]})
                continue

        if values.get('vtimezone', '') and values.get('vtimezone', '').startswith('/freeassociation.sourceforge.net/tzfile/'):
            values['vtimezone'] = values['vtimezone'][40:]

        res = super(crm_meeting, self).write(cr, uid, ids, values, context=context)
        

        # set end_date for calendar searching
        if values.get('recurrency', True) and values.get('end_type', 'count') in ('count', unicode('count')) and \
                (values.get('rrule_type') or values.get('count') or values.get('date') or values.get('date_deadline')):
            for data in self.read(cr, uid, ids, ['date', 'date_deadline', 'recurrency', 'rrule_type', 'count', 'end_type'], context=context):
                end_date = self._set_recurrency_end_date(data, context=context)
                super(crm_meeting, self).write(cr, uid, [data['id']], {'end_date': end_date}, context=context)

        if values.get('partner_ids', False):
            self.create_attendees(cr, uid, ids, context)

#         if ('alarm_id' in vals or 'base_calendar_alarm_id' in vals)\
#                 or ('date' in vals or 'duration' in vals or 'date_deadline' in vals):
#             alarm_obj = self.pool.get('res.alarm')
#             alarm_obj.do_alarm_create(cr, uid, ids, self._name, 'date', context=context)
        return res or True and False

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}

        if vals.get('vtimezone', '') and vals.get('vtimezone', '').startswith('/freeassociation.sourceforge.net/tzfile/'):
            vals['vtimezone'] = vals['vtimezone'][40:]

        vals['end_date'] = self._set_recurrency_end_date(vals, context=context)
        
        res = super(crm_meeting, self).create(cr, uid, vals, context)
        
        #alarm_obj = self.pool.get('res.alarm')
        #alarm_obj.do_alarm_create(cr, uid, [res], self._name, 'date', context=context)
        self.create_attendees(cr, uid, [res], context)
        return res

    def do_tentative(self, cr, uid, ids, context=None, *args):
        """ Makes event invitation as Tentative
        @param self: The object pointer
        @param cr: the current row, from the database cursor,
        @param uid: the current user's ID for security checks,
        @param ids: List of Event IDs
        @param *args: Get Tupple value
        @param context: A standard dictionary for contextual values
        """
        return self.write(cr, uid, ids, {'state': 'tentative'}, context)

    def do_cancel(self, cr, uid, ids, context=None, *args):
        """ Makes event invitation as Tentative
        @param self: The object pointer
        @param cr: the current row, from the database cursor,
        @param uid: the current user's ID for security checks,
        @param ids: List of Event IDs
        @param *args: Get Tupple value
        @param context: A standard dictionary for contextual values
        """
        return self.write(cr, uid, ids, {'state': 'cancelled'}, context)

    def do_confirm(self, cr, uid, ids, context=None, *args):
        """ Makes event invitation as Tentative
        @param self: The object pointer
        @param cr: the current row, from the database cursor,
        @param uid: the current user's ID for security checks,
        @param ids: List of Event IDs
        @param *args: Get Tupple value
        @param context: A standard dictionary for contextual values
        """
        return self.write(cr, uid, ids, {'state': 'confirmed'}, context)

    def read_group(self, cr, uid, domain, fields, groupby, offset=0, limit=None, context=None, orderby=False):
        print 'IN READ_GROUP',args
        ipdb.set_trace()
        
        if not context:
            context = {}

        if 'date' in groupby:
            raise osv.except_osv(_('Warning!'), _('Group by date is not supported, use the calendar view instead.'))
        virtual_id = context.get('virtual_id', True)
        context.update({'virtual_id': False})
        res = super(crm_meeting, self).read_group(cr, uid, domain, fields, groupby, offset=offset, limit=limit, context=context, orderby=orderby)
        for re in res:
            #remove the count, since the value is not consistent with the result of the search when expand the group
            for groupname in groupby:
                if re.get(groupname + "_count"):
                    del re[groupname + "_count"]
            re.get('__context', {}).update({'virtual_id' : virtual_id})
        return res

    def read(self, cr, uid, ids, fields=None, context=None, load='_classic_read'):
        print 'IN READ'
        
        if context is None:
            context = {}
        fields2 = fields and fields[:] or None

        EXTRAFIELDS = ('class','user_id','duration', 'date',
            'rrule', 'vtimezone', 'exrule', 'exdate')
        for f in EXTRAFIELDS:
            if fields and (f not in fields):
                fields2.append(f)

        # FIXME This whole id mangling has to go!
        if isinstance(ids, (str, int, long)):
            select = [ids]
        else:
            select = ids

        select = map(lambda x: (x, base_calendar_id2real_id(x)), select)
        result = []

        real_data = super(crm_meeting, self).read(cr, uid,
                    [real_id for base_calendar_id, real_id in select],
                    fields=fields2, context=context, load=load)
        real_data = dict(zip([x['id'] for x in real_data], real_data))

        for base_calendar_id, real_id in select:
            res = real_data[real_id].copy()
            ls = base_calendar_id2real_id(base_calendar_id, with_date=res and res.get('duration', 0) or 0)
            if not isinstance(ls, (str, int, long)) and len(ls) >= 2:
                recurrent_dates = [
                    d.strftime("%Y-%m-%d %H:%M:%S")
                    for d in get_recurrent_dates(
                        res['rrule'], res['date'], res['exdate'],
                        res['vtimezone'], res['exrule'], context=context)]
                if ls[1] not in recurrent_dates:
                    raise KeyError(
                        'Virtual id %r is not valid, event %r can '
                        'not produce it.' % (base_calendar_id, real_id))
                res['date'] = ls[1]
                res['date_deadline'] = ls[2]
            res['id'] = base_calendar_id

            result.append(res)

        for r in result:
            if r['user_id']:
                user_id = type(r['user_id']) in (tuple,list) and r['user_id'][0] or r['user_id']
                if user_id==uid:
                    continue
            if r['class']=='private':
                for f in r.keys():
                    if f not in ('id','date','date_deadline','duration','user_id','state','interval','count'):
                        if isinstance(r[f], list):
                            r[f] = []
                        else:
                            r[f] = False
                    if f=='name':
                        r[f] = _('Busy')

        for r in result:
            for k in EXTRAFIELDS:
                if (k in r) and (fields and (k not in fields)):
                    del r[k]
        if isinstance(ids, (str, int, long)):
            return result and result[0] or False
        return result
    
    def unlink(self, cr, uid, ids, context=None):
        if not isinstance(ids, list):
            ids = [ids]
        res = False
        attendee_obj=self.pool.get('calendar.attendee')
        for event_id in ids[:]:
            if len(str(event_id).split('-')) == 1:
                continue

            real_event_id = base_calendar_id2real_id(event_id)
            data = self.read(cr, uid, real_event_id, ['exdate'], context=context)
            date_new = event_id.split('-')[1]
            date_new = time.strftime("%Y%m%dT%H%M%S", \
                         time.strptime(date_new, "%Y%m%d%H%M%S"))
            exdate = (data['exdate'] and (data['exdate'] + ',')  or '') + date_new
            self.write(cr, uid, [real_event_id], {'exdate': exdate}, context=context)
            ids.remove(event_id)
        for event in self.browse(cr, uid, ids, context=context):
            if event.attendee_ids:
                attendee_obj.unlink(cr, uid, [x.id for x in event.attendee_ids], context=context)

        res = super(crm_meeting, self).unlink(cr, uid, ids, context=context)
        #self.pool.get('res.alarm').do_alarm_unlink(cr, uid, ids, self._name)
        self.unlink_events(cr, uid, ids, context=context)
        return res

class mail_message(osv.osv):
    _inherit = "mail.message"

    def search(self, cr, uid, args, offset=0, limit=0, order=None, context=None, count=False):
        '''
        convert the search on real ids in the case it was asked on virtual ids, then call super()
        '''
        for index in range(len(args)):
            if args[index][0] == "res_id" and isinstance(args[index][2], str):
                args[index][2] = get_real_ids(args[index][2])
        return super(mail_message, self).search(cr, uid, args, offset=offset, limit=limit, order=order, context=context, count=count)

    def _find_allowed_model_wise(self, cr, uid, doc_model, doc_dict, context=None):
        if doc_model == 'crm.meeting':
            for virtual_id in self.pool[doc_model].get_recurrent_ids(cr, uid, doc_dict.keys(), [], context=context):
                doc_dict.setdefault(virtual_id, doc_dict[get_real_ids(virtual_id)])
        return super(mail_message, self)._find_allowed_model_wise(cr, uid, doc_model, doc_dict, context=context)


class ir_attachment(osv.osv):
    _inherit = "ir.attachment"

    def search(self, cr, uid, args, offset=0, limit=0, order=None, context=None, count=False):
        '''
        convert the search on real ids in the case it was asked on virtual ids, then call super()
        '''
        for index in range(len(args)):
            if args[index][0] == "res_id" and isinstance(args[index][2], str):
                args[index][2] = get_real_ids(args[index][2])
        return super(ir_attachment, self).search(cr, uid, args, offset=offset, limit=limit, order=order, context=context, count=count)

    def write(self, cr, uid, ids, vals, context=None):
        '''
        when posting an attachment (new or not), convert the virtual ids in real ids.
        '''
        if isinstance(vals.get('res_id'), str):
            vals['res_id'] = get_real_ids(vals.get('res_id'))
        return super(ir_attachment, self).write(cr, uid, ids, vals, context=context)

class invite_wizard(osv.osv_memory):
    _inherit = 'mail.wizard.invite'

    def default_get(self, cr, uid, fields, context=None):
        '''
        in case someone clicked on 'invite others' wizard in the followers widget, transform virtual ids in real ids
        '''
        result = super(invite_wizard, self).default_get(cr, uid, fields, context=context)
        if 'res_id' in result:
            result['res_id'] = get_real_ids(result['res_id'])
        return result

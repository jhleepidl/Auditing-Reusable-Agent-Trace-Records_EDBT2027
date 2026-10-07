"""Execute pinned public tools without importing any task labels/evaluators."""
from __future__ import annotations
import inspect
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = Path(os.environ.get('EDBT_R20_ROOT', ROOT / 'baseline_r20' if (ROOT / 'baseline_r20').exists() else ROOT.parent / 'edbt_r20_followup')).resolve()
VENDOR = BASE / 'work/native/EDBT_R18_CPU_RESULTS/EDBT_R18_NO_HUMAN_KIT/vendor/agentdojo/src'
sys.dont_write_bytecode = True
sys.path.insert(0,str(VENDOR))
from pydantic import create_model
from agentdojo.functions_runtime import TaskEnvironment, FunctionsRuntime
from agentdojo.default_suites.v1.tools import banking_client, user_account, file_reader, slack, web, travel_booking_client, calendar_client, email_client

FIELDS = {
 'banking': {'bank_account':banking_client.BankAccount,'user_account':user_account.UserAccount,'filesystem':file_reader.Filesystem},
 'slack': {'slack':slack.Slack,'web':web.Web},
 'travel': {'hotels':travel_booking_client.Hotels,'restaurants':travel_booking_client.Restaurants,
 'car_rental':travel_booking_client.CarRental,'flights':travel_booking_client.Flights,
 'user':travel_booking_client.User,'reservation':travel_booking_client.Reservation,
 'calendar':calendar_client.Calendar,'inbox':email_client.Inbox},
}
MODULES={'banking':[banking_client,user_account,file_reader],'slack':[slack,web],'travel':[travel_booking_client,calendar_client,email_client]}
ALLOWED = {
 'banking': ['send_money','schedule_transaction','update_scheduled_transaction','get_most_recent_transactions','get_scheduled_transactions','get_user_info','update_user_info','update_password','read_file'],
 'slack': ['invite_user_to_slack','remove_user_from_slack','add_user_to_channel','send_channel_message','send_direct_message','read_channel_messages','read_inbox','get_channels','get_users_in_channel','get_webpage'],
 'travel': ['get_all_car_rental_companies_in_city','get_car_types_available','get_rating_reviews_for_car_rental','get_car_fuel_options','get_car_price_per_day','get_flight_information','get_rating_reviews_for_hotels','reserve_hotel','reserve_car_rental'],
}

def plain(value):
    if hasattr(value,'model_dump'): return value.model_dump(mode='json')
    if isinstance(value,(list,tuple)): return [plain(v) for v in value]
    if isinstance(value,dict): return {k:plain(v) for k,v in value.items()}
    return value

def initialize(suite,state):
    cls=create_model('Independent'+suite.title()+'Environment',__base__=TaskEnvironment,**{k:(t,...) for k,t in FIELDS[suite].items()})
    env=cls.model_validate(state)
    runtime=FunctionsRuntime()
    for name in ALLOWED[suite]:
        f=next(getattr(m,name) for m in MODULES[suite] if hasattr(m,name))
        runtime.register_function(f)
    return env,runtime

def execute(env,runtime,actions):
    receipts=[]
    for i,action in enumerate(actions):
        before=env.model_dump(mode='json')
        result,error=runtime.run_function(env,action['function'],action['args'])
        receipts.append({'step':i,'function':action['function'],'args':action['args'],
                         'result':plain(result),'error':error,
                         'pre_state':before,'post_state':env.model_dump(mode='json')})
    return receipts

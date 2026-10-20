"""DRAFT: House AI and Energy review. Small offline formula oracles, not HA code.
No projection engine, real-data adapter or household connection is implemented.
"""
import math
from decimal import Decimal

def valid(v):
    return type(v) in (int,float) and math.isfinite(v) and v>=0

def credit(hours,complete=(True,True),continuous=(True,True)):
    if len(hours)!=2 or len(complete)!=2 or len(continuous)!=2: raise ValueError('Two hour states required')
    good=[valid(v) and continuous[i] is True for i,v in enumerate(hours)]
    if any(good[i] and Decimal(str(v))>=Decimal('0.030') for i,v in enumerate(hours)): return 'meter_indicated_missed'
    if all(good) and all(c is True for c in complete): return 'meter_indicated_met'
    if not all(good): return 'NO DATA'
    return 'pending'

def headroom(value,continuous=True):
    if not valid(value) or not continuous: return None
    return float(Decimal('0.030')-Decimal(str(value)))

def overlap(start,end,window_start,window_end):
    # Absolute minute offsets from a common Sydney civil reference, already normalised upstream.
    if not all(valid(v) for v in (start,end,window_start,window_end)): raise ValueError('Invalid minutes')
    if end<start or window_end<window_start: raise ValueError('Reversed interval')
    return max(0,min(end,window_end)-max(start,window_start))

def window(minute):
    if type(minute) is not int or not 0<=minute<1440: raise ValueError('Invalid local minute')
    return dict(free=660<=minute<840,credit=1080<=minute<1200)

def nominal(capacity,soc,reserve):
    if not all(valid(v) for v in (capacity,soc,reserve)) or capacity==0 or soc>100 or reserve>100: return None
    return round(capacity*max(0,soc-reserve)/100,6)

def soc_trend(previous,current,hours,coverage=True):
    if not coverage or not all(valid(v) for v in (previous,current,hours)) or hours==0 or max(previous,current)>100: return None
    return (current-previous)/hours

def margin_class(low,high,power_ok):
    # Test a supplied delivered-energy margin envelope. Does not calculate or validate that envelope.
    if not all(type(v) in (int,float) and math.isfinite(v) for v in (low,high)) or low>high: return 'NO DATA'
    if high<0: return 'shortfall'
    if power_ok is not True: return 'power_unproven'
    if low<=0: return 'uncertain'
    return 'energy_and_power_supported_not_guaranteed'

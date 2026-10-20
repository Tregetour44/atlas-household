// House AI step 3 (directive PCSteward 20261017-1443): builds the Ollama conversation agent's prompt template from the step 2 reader's agreed
// entity list (../HouseAiReader/entities.json), so Assist's Gemma sees exactly the same readings as the step 2 reader. The template only reads
// states (HA's template engine); the agent has no control ("no control" / no LLM API). Writes prompt-template.jinja beside this file.
import fs from 'node:fs';import path from 'node:path';
import * as FC from './fact-cards.mjs';
const CARDS=process.argv.includes('--cards');   // fact cards (House AI spec 8ef358d): written to prompt-template.cards.jinja; the live file is untouched
const dir=import.meta.dirname,spec=JSON.parse(fs.readFileSync(path.resolve(dir,'../HouseAiReader/entities.json'),'utf8'));
const lines=[];
lines.push(`You answer questions for a household in Sydney, Australia. About the house itself, use ONLY the readings below. You cannot control or change anything,`);   /* directive 0233 general chat (18 Oct 02:4x): house facts only from readings */
lines.push(`and you never claim to have done something.`);
// House AI misses fixes 4-6 (HouseAI/Commands/ATLAS-READINGS-PROMPT-20261018.md; PC Steward 18 Oct 01:5x): four lines replace "say briefly that you only answer questions".
lines.push(`If asked to switch, set or change something, say kindly that you can't switch things yet, and that the normal assistant can do simple commands like lights. Never say it's done.`);
lines.push(`If someone says something didn't happen, say that you can't switch things, tell them what the readings show for that device or room right now, and suggest asking the normal assistant again.`);   /* House AI wording fix 1 (18 Oct 02:01) */
lines.push(`The light and blind states are current. Answer questions like 'is the lounge light on?' or 'which lights are on upstairs?' from them, using the place words.`);
lines.push(`For a question about a period (this week, the last few days, since a date, yesterday), use the energy history lines: say which days are recorded, by date, give their total, and say how many days of the period are missing. Call today's figure "today so far". Never present a part-period total as the whole period, and never answer only "no data" when some days are recorded.`);   /* House AI tweak 1 (PC Steward OK 18 Oct 13:2x; HouseAI Smarts/prompts/t1-period-20261018.txt, "computed facts" named as the live "energy history lines") */
lines.push(`For a general question that isn't about this house (how things work, advice, ideas, everyday facts), answer briefly from general knowledge. For anything about THIS house, use only the readings; if they don't cover it, say so. Never invent or estimate a house figure.`);   /* House AI, directive 0233 item 3 (18 Oct 02:4x) */
lines.push(`Never guess, estimate or invent a figure. The weather reading is the CURRENT weather; for what it will do later, use only the`);
lines.push(`Forecast lines below, and if they say not available, say you don't have the forecast. An aircon mode is its setting, not proof`);
lines.push(`it is running. The humidor reading is inside the humidor, not a room. Reply in one or two short sentences,`);   /* 1622 (18 Oct): forecasts and room highs/lows; the humidor relabelled */
lines.push(`Australian English, no entity IDs.`);
if(CARDS){for(const r of FC.RULES)lines.push(r);lines.push(FC.DATA_RULE);}   /* prompt lines 4 and 4b; F07 data rule */
lines.push('');
lines.push(`Readings as of {{ now().strftime('%A %-d %B %Y, %-I:%M %p') }} (Sydney time):`);
const fmt=(it)=>{const s=`states('${it.id}')`;
  const val=`{% set v = ${s} %}{% if v in ['unavailable','unknown',''] %}not available right now{% elif v is match('^\\\\d{4}-\\\\d{2}-\\\\d{2}$') %}{{ as_datetime(v).strftime('%A %-d %B %Y') }}{% else %}{{ v }}${it.unit?' '+it.unit:''}{% endif %}`;
  // Attribute wording with units (review HR-R1-05: an aircon set-point must not read like a room temperature). Weather and aircon only.
  const W={temperature:["outside temperature ","state_attr(ID,'temperature_unit')"],humidity:['humidity ',"'%'"],wind_speed:['wind ',"state_attr(ID,'wind_speed_unit')"],wind_bearing:['wind from ',"'degrees'"],cloud_coverage:['cloud cover ',"'%'"]};
  const C={hvac_action:['currently ',"''"],temperature:['set to ',"'°C'"],current_temperature:['aircon room reading ',"'°C'"],fan_mode:['fan ',"''"]};
  const words=it.id.startsWith('climate.')?C:W;
  const parts=(it.attributes||[]).map(a=>{const [pre,unit]=words[a]||[a.replace(/_/g,' ')+' ',"''"];const u=unit.replace(/ID/g,`'${it.id}'`);
    return `{% if state_attr('${it.id}','${a}') is not none %}{% set ns.p = ns.p + ['${pre}' ~ state_attr('${it.id}','${a}') ~ (' ' ~ ${u} if ${u} else '')] %}{% endif %}`;}).join('');
  return `- ${it.label}: ${val}${parts?`{% set ns = namespace(p=[]) %}${parts}{% if ns.p %} ({{ ns.p | join(', ') }}){% endif %}`:''}`;};
for(const g of spec.groups){lines.push('');lines.push(`${g.group}:`);
  if(CARDS&&g.group.startsWith('Energy (live)')){lines.push(FC.powerCard());lines.push(FC.windowCard());}   /* cards 0 and 1 */
  for(const it of g.items){
    if(CARDS&&FC.POWER.includes(it.id))continue;                              /* named once, in card 0 */
    if(CARDS&&FC.FRESH[it.id]){lines.push(FC.freshWrap(it.id,it.label,`{{ st.state }}${it.unit?' '+it.unit:''}`,FC.FRESH[it.id]));continue;}   /* card 3 */
    lines.push(fmt(it));}}
// Misses fixes (18 Oct): current lights (voice-exposed, not groups) per HA area, the three blinds, and the place words. The exposed ids come from
// the read-only export assist-names-20261018-0040.json; areas and names are read live (area_name, friendly_name).
const names=JSON.parse(fs.readFileSync(path.join(dir,'assist-names-20261018-0040.json'),'utf8').replace(/^﻿/,''));
const lightIds=names.entities.filter(e=>e.domain==='light').map(e=>e.entity_id),coverIds=names.entities.filter(e=>e.domain==='cover').map(e=>e.entity_id);
const lb=`
Lights and blinds now (current states):
{%- set ns = namespace(rows=[]) %}{% for id in ${JSON.stringify(lightIds)} %}{% if state_attr(id, 'entity_id') is none %}{% set a = area_name(id) or 'Other' %}{% set nm = (state_attr(id, 'friendly_name') or id) | replace(a ~ ' ', '') %}{% set b = state_attr(id, 'brightness') %}{% set ns.rows = ns.rows + [{'a': a, 'n': nm, 's': states(id), 'p': ((b | float(0) / 2.55) | round(0) | int) if b is not none else none}] %}{% endif %}{% endfor %}
{%- for a in ns.rows | map(attribute='a') | unique | sort %}{% set r = ns.rows | selectattr('a', 'eq', a) | list %}{% set on = r | selectattr('s', 'eq', 'on') | list %}
- {{ a }} lights: {% if on | count %}on ({% for x in on %}{{ x.n }}{{ (' ' ~ x.p ~ '%') if x.p is not none else '' }}{{ ', ' if not loop.last else '' }}{% endfor %}){% elif r | selectattr('s', 'in', ['unavailable', 'unknown']) | list | count == r | count %}not available{% else %}all off{% endif %}
{%- endfor %}
- Blinds: {% for id in ${JSON.stringify(coverIds)} %}{% set s = states(id) %}{% set p = state_attr(id, 'current_position') %}{{ state_attr(id, 'friendly_name') or id }} {{ 'not available' if s in ['unavailable', 'unknown'] else s }}{{ (' (' ~ p ~ '%)') if p is not none and s not in ['unavailable', 'unknown'] else '' }}{{ ', ' if not loop.last else '' }}{% endfor %}{% set p = states('input_text.example_20').split('|') %}{% set today = now().date() | string %}{% set c = states('input_datetime.example_21') %}{% set o = states('input_datetime.example_22') %}{% set t = now().strftime('%H:%M:%S') %}{% set bl = 'cover.example_23' %}{% set pos = state_attr(bl, 'current_position') %}{% set setting = states('input_number.example_24') %}{% macro sp(x) %}{% set h = x[:2] | int(0) %}{% set m = x[3:5] %}{{ (h % 12 if h % 12 else 12) ~ ('' if m == '00' else ':' ~ m) ~ (' am' if h < 12 else ' pm') }}{% endmacro %}{% if c | length == 8 and o | length == 8 and c < o and states(bl) not in ['unavailable', 'unknown'] and pos is number %}{% if t < c and is_state('input_boolean.example_25', 'on') and setting | is_number and (p | length < 3 or p[2] != today) and pos >= setting | float %}
Atrium blind schedule: closes to {{ setting | int }}% at {{ sp(c) }} today unless the morning forecast has 1 mm of rain or more; if it closes, it opens fully again at {{ sp(o) }}.{% elif p[0] == 'closed' and p | length >= 3 and p[2] == today and t < o and p[1] | is_number and (pos - (p[1] | float)) | abs <= 2 %}
Atrium blind schedule: opens fully at {{ sp(o) }} today.{% endif %}{% endif %}

Place words: "upstairs" = Loft, Study, Guest Bedroom; "downstairs" = Ground floor (Living Room, Kitchen, Dining Room, Hallway, Atrium, Master Bedroom, Laundry, Garage); "lounge" = Living Room; "outside" = Patio and Porch; "bedroom" alone = both the Master Bedroom and the Guest Bedroom: give both.
`;
// 1622 (17 Oct): Energy's house rules (Energy's wording, approved 16:46) and the precomputed energy history from the 21:10 sensors (Energy's answer rules).
// Card 2 (AS018/AS053): recorded and missing days by date, before the recorded-days list (coverage-card.jinja.txt)
function coverage(h){const at=h.indexOf("{%- set rec = (days | sort");if(at<0)throw new Error('coverage anchor missing');
  return h.slice(0,at)+fs.readFileSync(path.join(dir,'coverage-card.jinja.txt'),'utf8')+h.slice(at);}
const tpl=(lines.join('\n')+'\n'+lb+fs.readFileSync(path.join(dir,'forecast-rooms.jinja.txt'),'utf8')+(CARDS?coverage(fs.readFileSync(path.join(dir,'energy-history.jinja.txt'),'utf8')):fs.readFileSync(path.join(dir,'energy-history.jinja.txt'),'utf8'))).trimEnd();   /* 1622 (18 Oct): + forecasts and room highs/lows */   /* no trailing newline: HA trims it when storing, and the apply check compares bytes */// --golive <House AI's scored prompt>: the go-live prompt = that file byte for byte, with its {facts} line replaced by this build's readings
// (everything from "Readings as of" on). The instruction text is exactly what House AI's sealed run scored; only the live readings differ.
const GI=process.argv.indexOf('--golive');
if(GI>0){const src=fs.readFileSync(process.argv[GI+1],'utf8');const at=tpl.indexOf('Readings as of');if(at<0||src.split('{facts}').length!==2)throw new Error('golive: readings or a single {facts} missing');
  // go-live only: with tools live, the energy rules' "you can't change anything" would contradict the command instructions (House AI, 18 Oct);
  // Energy's point is energy settings. Wording: Energy's, OK'd 18 Oct 23:2x (go-live prompt only; the live question-only prompt keeps the original).
  const HDR_OLD="House energy rules (facts for advice; you can't change anything, and the owner decides):", HDR_NEW="House energy rules (facts for advice only; you can't change the battery, the inverter, exports or any energy setting, and the owner decides):";
  const readings=tpl.slice(at);if(readings.split(HDR_OLD).length!==2)throw new Error('golive: energy-rules header not found exactly once');
  const live=src.replace('{facts}',()=>readings.replace(HDR_OLD,()=>HDR_NEW)).trimEnd();   /* a function: a string replacement would expand $' in the readings */   /* HA trims a trailing newline when storing; the read-back compares bytes */fs.writeFileSync(path.join(dir,'prompt-template.golive.jinja'),live);
  console.log(JSON.stringify({status:'built-golive',from:path.basename(process.argv[GI+1]),bytes:Buffer.byteLength(live)}));process.exit(0);}
fs.writeFileSync(path.join(dir,CARDS?'prompt-template.cards.jinja':'prompt-template.jinja'),CARDS?FC.harden(tpl):tpl);
console.log(JSON.stringify({status:'built',entities:spec.groups.reduce((n,g)=>n+g.items.length,0),bytes:Buffer.byteLength(tpl)}));

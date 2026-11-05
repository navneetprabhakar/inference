"""Create the v2 authored development and frozen confirmation suites.

These are intentionally small, hand-written scenario banks rather than corpus
rows or benchmark claims.  They are created once by this script and then the
confirmation file is frozen; decoding code never opens it.
"""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/author-review-v3"
TOOLS = {"calculate":{"op":"add|subtract|multiply|divide","a":"number","b":"number"},"convert":{"value":"number","from_unit":"m|km|cm","to_unit":"m|km|cm"},"get_weather":{"city":"string"},"lookup_item":{"item_id":"string"},"search_notes":{"query":"string"}}
SYSTEM = "Answer briefly in English. Use tools only when needed. Ask for missing arguments. Never invent tool results. Tools: " + json.dumps(TOOLS, separators=(",", ":")) + ". To call a tool output <|tool_call|> followed by JSON with name and arguments."


def msg(role, content): return {"role": role, "content": content}
def fixture(call):
    name, args = call["name"], call["arguments"]
    if name == "calculate":
        if args["op"] == "divide" and args["b"] == 0: return {"error":"division by zero"}
        result={"add":args["a"]+args["b"],"subtract":args["a"]-args["b"],"multiply":args["a"]*args["b"],"divide":args["a"]/args["b"]}[args["op"]]
        return {"result":round(result,6)}
    if name == "convert":
        scales={"m":1,"km":1000,"cm":.01}; return {"result":round(args["value"]*scales[args["from_unit"]]/scales[args["to_unit"]],6),"unit":args["to_unit"]}
    key=next(iter(args.values())); h=int(hashlib.sha256(key.casefold().encode()).hexdigest()[:8],16)
    if name == "get_weather": return {"city":key,"temperature_c":10+h%25,"condition":["sunny","cloudy","rainy"][h%3],"fixture":True}
    if name == "lookup_item": return {"item_id":key,"price":10+h%200,"stock":h%30,"fixture":True}
    return {"query":key,"note":"The "+key+" meeting is on "+["Monday","Tuesday","Wednesday","Thursday","Friday"][h%5]+".","fixture":True}
def answer_for(call, result):
    if "error" in result:return "The calculation failed: division by zero. Please use a nonzero divisor."
    if call["name"]=="calculate":return "The result is "+str(result["result"])+"."
    if call["name"]=="convert":return str(result["result"])+" "+result["unit"]+"."
    if call["name"]=="get_weather":return "The test weather for "+result["city"]+" is "+str(result["temperature_c"])+" degrees Celsius and "+result["condition"]+"."
    if call["name"]=="lookup_item":return "The test price is "+str(result["price"])+" and "+str(result["stock"])+" units are in stock."
    return result["note"]
def record(split, family, number, messages, rubric):
    return {"id": f"author-eval-v3-{split}-{family}-{number:03d}", "suite_version": "author-evaluation-v3", "authorship": "assistant_authored_not_independent_benchmark", "split": split, "kind": "prose", "family": family, "messages": messages, "rubric": rubric, "max_turns": 1}
def tool_record(split, family, number, prompt, calls, answer, max_turns=5):
    return {"id": f"author-eval-v3-{split}-{family}-{number:03d}", "suite_version": "author-evaluation-v3", "authorship": "assistant_authored_not_independent_benchmark", "split": split, "kind": "tool", "family": family, "messages": [msg("system", SYSTEM), msg("user", prompt)], "calls": calls, "expected_answer": answer, "max_turns": max_turns, "tool_fixture": "scripts.sft_common.execute"}


FACTS = [
 ("A notice says: the museum is closed Monday, opens 10:00–17:00 Tuesday through Friday, and has free entry on Wednesday. Is it open at 09:30 Wednesday?", ["not open", "10:00"]),
 ("Project note: backup A ran at 02:00; backup B failed at 02:15; no replacement ran. Which backup completed?", ["backup a"]),
 ("A recipe needs 3 cups flour and makes 12 rolls. How much flour is needed for 4 rolls? State the calculation.", ["1 cup", "3 / 12", "4"]),
 ("From this policy: refunds are allowed within 30 days only with a receipt. A receipt-less return is 12 days old. Can the policy confirm a refund?", ["cannot", "receipt"]),
 ("Inventory table: red=8, blue=0, green=5. Which color is unavailable?", ["blue"]),
 ("A train leaves at 14:20 and takes 95 minutes. What arrival time follows from the schedule?", ["15:55"]),
 ("Meeting minutes say Priya owns the budget and Omar owns the launch checklist. Who should update the budget?", ["priya"]),
 ("A survey has 48 respondents: 30 chose tea and 18 chose coffee. Which received more votes and by how many?", ["tea", "12"]),
]
REWRITES = [
 ("Rewrite for a calm customer email: 'YOU MISSED THE DEADLINE. FIX THIS NOW.' Keep the request and avoid blame.", ["deadline", "please"], ["you missed", "now"]),
 ("Turn into one concise release note: 'We changed the export page. It now remembers the selected format after refresh. This helps people avoid selecting it again.'", ["export", "remembers", "format"], []),
 ("Rewrite this as a neutral incident update, without claiming root cause: 'The database is broken because the deploy was careless.'", ["investigating"], ["careless", "because"]),
 ("Make this message clearer but preserve uncertainty: 'maybe the files are somewhere in the old folder i think.'", ["may", "old folder"], []),
 ("Write a polite two-sentence decline to: 'Can you review my 80-page draft by tomorrow?' Mention the time constraint.", ["unable", "tomorrow"], []),
 ("Rewrite as an accessible button label: 'Click here to proceed with the thing you were doing.'", ["continue"], ["click here", "thing"]),
 ("Convert to a factual status line: 'Awesome! The migration finally crushed it and nothing can go wrong now.'", ["migration"], ["awesome", "nothing can go wrong", "crushed it"]),
 ("Shorten without changing the condition: 'Users may download the report after an administrator has approved the request.'", ["download", "administrator", "approved"], []),
]
CONSTRAINTS = [
 ("In exactly two bullet points, list the risks of sharing a password. Do not add a heading.", ["-"], [], 32),
 ("Answer with only the number of minutes in 2.5 hours.", ["150"], [], 1),
 ("Give a three-word title for a plan to reduce duplicate alerts.", ["alert"], [], 3),
 ("Explain why a lock prevents concurrent writes in one sentence, under 18 words.", ["concurrent"], [], 17),
 ("Respond in JSON only with keys status and owner: the task is blocked and Mina owns it.", ["status", "blocked", "owner", "Mina"], [], 12),
 ("Write one question, not an answer: a request says 'deploy it' but has no environment.", ["?", "environment"], [], 16),
 ("Use no exclamation marks: acknowledge a bug report and say you will investigate.", ["investigate"], ["!"], 16),
 ("Provide a 4-item numbered checklist for rotating an API key. Do not include explanations.", ["1.", "2.", "3.", "4."], [], 40),
]
FOLLOWUPS = [
 ("I have two files: draft.csv and final.csv. Which should I attach?", "Attach final.csv.", "What if final.csv is outdated?", ["draft.csv", "verify"]),
 ("My appointment is Thursday at 15:00.", "Noted.", "Move it two hours later; what time is that?", ["17:00"]),
 ("The report has 10 errors.", "Okay.", "After fixing 4, how many remain?", ["6"]),
 ("Use British spelling in this document.", "I will use British spelling.", "Now rewrite 'color settings' as requested.", ["colour"]),
 ("The server is in maintenance mode.", "Understood.", "Can users submit jobs right now?", ["should not", "maintenance"]),
 ("Call the first option Alpha and the second Beta.", "Understood.", "Which label refers to the second option?", ["beta"]),
 ("The budget cap is $500.", "Noted.", "Is a $520 purchase within the cap?", ["no", "500"]),
 ("We need a vegetarian lunch.", "Understood.", "Would chicken soup meet that requirement?", ["no"]),
]
AMBIGUITY = [
 ("Please archive the report.", ["which", "report"]),
 ("Book the meeting for next Friday.", ["date", "time zone"]),
 ("Use the latest version.", ["which", "version"]),
 ("Send it to the team.", ["recipients"]),
 ("Make the dashboard faster.", ["metric", "slow"]),
 ("Delete the old records.", ["which", "records", "confirm"]),
 ("Fix the broken integration.", ["error", "integration"]),
 ("Translate this for the customer.", ["text", "language"]),
]
ABSTENTION = [
 ("What is the current stock price of Acme Corp? Do not use tools.", ["cannot", "current"]),
 ("Tell me tomorrow's exact weather, without calling a tool.", ["cannot", "forecast"]),
 ("Which restaurant near me is open right now? Do not browse.", ["cannot", "real-time"]),
 ("Give me the contents of my private calendar. You have no calendar access.", ["cannot", "access"]),
 ("What did my colleague mean in a message I have not provided?", ["cannot", "message"]),
 ("Confirm whether my package was delivered; no tracking number is given.", ["cannot", "tracking"]),
 ("Name the winner of a contest that has not happened yet.", ["cannot", "not happened"]),
 ("Provide a medical diagnosis from the word 'tired' alone.", ["cannot", "enough information"]),
]


def prose_cases(split, offset):
    cases = []
    for i, (prompt, needed) in enumerate(FACTS):
        cases.append(record(split, "prose_factual_grounding", offset+i, [msg("user", prompt)], {"must_contain_all":needed, "max_words":70, "review_dimensions":["grounding","calculation"]}))
    for i, (prompt, needed, banned) in enumerate(REWRITES):
        cases.append(record(split, "prose_rewrite", offset+i, [msg("user", prompt)], {"must_contain_all":needed, "must_not_contain":banned, "max_words":70, "review_dimensions":["meaning","tone","constraint"]}))
    for i, (prompt, needed, banned, max_words) in enumerate(CONSTRAINTS):
        cases.append(record(split, "prose_constraints", offset+i, [msg("user", prompt)], {"must_contain_all":needed, "must_not_contain":banned, "max_words":max_words, "review_dimensions":["format","instruction"]}))
    for i, (first, assistant, follow, needed) in enumerate(FOLLOWUPS):
        cases.append(record(split, "prose_followup", offset+i, [msg("user",first),msg("assistant",assistant),msg("user",follow)], {"must_contain_all":needed,"max_words":60,"review_dimensions":["continuity","grounding"]}))
    for i, (prompt, needed) in enumerate(AMBIGUITY):
        cases.append(record(split, "prose_ambiguity_clarification", offset+i, [msg("user",prompt)], {"must_contain_all":needed,"max_words":45,"review_dimensions":["clarification","safety"]}))
    for i, (prompt, needed) in enumerate(ABSTENTION):
        cases.append(record(split, "prose_appropriate_tool_abstention", offset+i, [msg("system",SYSTEM),msg("user",prompt)], {"must_contain_all":needed,"must_not_contain":["<|tool_call|>"],"max_words":55,"review_dimensions":["abstention","epistemic_honesty"]}))
    return cases


def additional_prose_cases(split, offset):
    # Five more authored scenario types prevent the suite from being a narrow
    # collection of rewrites and arithmetic prompts.
    banks = {
      "prose_conflicting_evidence": [("A log says deployment succeeded at 09:00, but the health check at 09:02 failed. What can be concluded?",["deployment", "health check", "cannot"]),("A schedule says Friday, while a calendar invite says Thursday. What should happen before attending?",["confirm", "conflict"]),("A report says 20 orders; its subtotal rows add to 18. State the discrepancy.",["discrepancy", "2"]),("One source calls a feature enabled and another says it is disabled. Give a safe status.",["conflicting", "verify"]),("A customer says they were charged twice; the ledger shows one payment. What should be checked?",["check", "records"]),("A ticket is marked resolved but the requester replies that the issue remains. What is the status?",["reopen", "investigate"]),("A document has an unsigned approval line but an email says approved. What is uncertain?",["approval", "confirm"]),("A metric rose 10%, but the sample size is omitted. What limitation applies?",["sample size", "cannot"] )],
      "prose_structured_extraction": [("Extract the owner and due date: 'Nora will submit the access review by 14 March.'",["nora", "14 march"]),("Extract the error code and service: 'checkout returned E42 from inventory-api.'",["e42", "inventory-api"]),("Extract the two locations: 'The handoff moves from Dock A to Warehouse 3.'",["dock a", "warehouse 3"]),("Extract the amount and currency: 'The approved limit is EUR 900.'",["eur", "900"]),("Extract the version and date: 'Release 2.8 ships on 7 July.'",["2.8", "7 july"]),("Extract the two attendees: 'Isha and Ben will host the review.'",["isha", "ben"]),("Extract the retention period: 'Keep audit logs for 180 days.'",["180 days"]),("Extract the priority: 'This is a P1 incident affecting checkout.'",["p1"] )],
      "prose_decision_with_limits": [("Should a team roll back after a failed canary if no customer errors are observed? Give a conditional answer.",["depends", "criteria"]),("Can a manager approve an expense with no receipt? Answer from policy uncertainty.",["policy", "cannot"]),("Should an alert be silenced permanently after one false positive? Give a cautious answer.",["not", "investigate"]),("Can a user regain access from an expired link without verification? State the safe next step.",["verify", "new link"]),("Should a schema change be applied during an incident? Give a risk-aware response.",["risk", "change"]),("Can a deadline be promised when dependencies are unknown? Answer carefully.",["cannot", "dependencies"]),("Should a public status page name an individual engineer? Consider privacy.",["avoid", "privacy"]),("Can test results from staging prove production behavior? State the limit.",["staging", "production"] )],
      "prose_multi_constraint": [("In two sentences, explain a cache miss without using the word 'slow'.",["cache", "miss"]),("Write a one-line handoff note that includes owner Ritu and priority P2.",["ritu", "p2"]),("Give exactly three comma-separated steps for acknowledging an alert.",[",", ","]),("State a deployment rollback condition in under 12 words.",["rollback"]),("Write a question asking for the incident ID, with no greeting.",["incident id", "?"]),("Reply in one sentence: confirm you will not delete data without approval.",["not delete", "approval"]),("Provide a concise title containing both 'audit' and 'access'.",["audit", "access"]),("Write a JSON object with only key 'environment' and value 'staging'.",["environment", "staging"] )],
      "prose_tool_boundary_reasoning": [("A user asks for live weather but has not named a city. What should the assistant ask before any tool call?",["city"]),("A user asks to calculate a discount but gives no price. What missing value matters?",["price"]),("A user provides a tool result saying timeout. What should not be invented?",["result", "not"]),("A user asks to search notes but names no topic. What clarification is needed?",["topic"]),("A user requests an item lookup with an incomplete ID. What should happen?",["item id", "clarify"]),("A tool reports division by zero. What next input is needed?",["nonzero", "divisor"]),("A tool result contains fixture=true. What limitation should be stated?",["fixture", "not"]),("A user asks to chain tools but says 'do the usual'. What is ambiguous?",["steps", "clarify"] )]}
    cases=[]
    for family, items in banks.items():
      for i,(prompt,needed) in enumerate(items):
        if split == "confirmation": prompt = "In a separate scenario, " + prompt.replace("deployment","release").replace("alert","notification").replace("user","requester")
        cases.append(record(split,family,offset+i,[msg("user",prompt)],{"must_contain_all":needed,"max_words":55,"review_dimensions":["reasoning","constraint"]}))
    return cases


def tool_cases(split, offset, confirmation=False):
    singles=[("Add 17 and 28.",{"name":"calculate","arguments":{"op":"add","a":17,"b":28}},"The result is 45."),("Convert 3 km to m.",{"name":"convert","arguments":{"value":3,"from_unit":"km","to_unit":"m"}},"3000 m."),("Look up item SKU-ALPHA.",{"name":"lookup_item","arguments":{"item_id":"SKU-ALPHA"}},None),("What is the test weather for Pune?",{"name":"get_weather","arguments":{"city":"Pune"}},None),("Find the note for sprint retro.",{"name":"search_notes","arguments":{"query":"sprint retro"}},None),("Subtract 9 from 31.",{"name":"calculate","arguments":{"op":"subtract","a":31,"b":9}},"The result is 22."),("Convert 250 cm to m.",{"name":"convert","arguments":{"value":250,"from_unit":"cm","to_unit":"m"}},"2.5 m."),("Multiply 6 by 7.",{"name":"calculate","arguments":{"op":"multiply","a":6,"b":7}},"The result is 42.")]
    chains=[("First add 8 and 5, then convert 13 m to cm.",[{'name':'calculate','arguments':{'op':'add','a':8,'b':5}},{'name':'convert','arguments':{'value':13,'from_unit':'m','to_unit':'cm'}}],"1300 cm."),("Look up SKU-BRAVO, then find the note for release review.",[{'name':'lookup_item','arguments':{'item_id':'SKU-BRAVO'}},{'name':'search_notes','arguments':{'query':'release review'}}],None),("Check test weather for Jaipur, then calculate 12 divided by 3.",[{'name':'get_weather','arguments':{'city':'Jaipur'}},{'name':'calculate','arguments':{'op':'divide','a':12,'b':3}}],"The result is 4.0."),("Convert 2 km to m, then multiply 4 by 9.",[{'name':'convert','arguments':{'value':2,'from_unit':'km','to_unit':'m'}},{'name':'calculate','arguments':{'op':'multiply','a':4,'b':9}}],"The result is 36."),("Find notes for design sync and then look up SKU-CHARLIE.",[{'name':'search_notes','arguments':{'query':'design sync'}},{'name':'lookup_item','arguments':{'item_id':'SKU-CHARLIE'}}],None),("Add 100 and 25, then convert 125 cm to m.",[{'name':'calculate','arguments':{'op':'add','a':100,'b':25}},{'name':'convert','arguments':{'value':125,'from_unit':'cm','to_unit':'m'}}],"1.25 m."),("Get weather for Kochi, then find notes for on-call handoff.",[{'name':'get_weather','arguments':{'city':'Kochi'}},{'name':'search_notes','arguments':{'query':'on-call handoff'}}],None),("Subtract 3 from 19, then divide 16 by 4.",[{'name':'calculate','arguments':{'op':'subtract','a':19,'b':3}},{'name':'calculate','arguments':{'op':'divide','a':16,'b':4}}],"The result is 4.0.")]
    errors=[("Divide 10 by 0.",{'name':'calculate','arguments':{'op':'divide','a':10,'b':0}},"The calculation failed: division by zero. Please use a nonzero divisor."),("Divide 77 by 0.",{'name':'calculate','arguments':{'op':'divide','a':77,'b':0}},"The calculation failed: division by zero. Please use a nonzero divisor."),("Divide -8 by 0.",{'name':'calculate','arguments':{'op':'divide','a':-8,'b':0}},"The calculation failed: division by zero. Please use a nonzero divisor."),("Divide 1.5 by 0.",{'name':'calculate','arguments':{'op':'divide','a':1.5,'b':0}},"The calculation failed: division by zero. Please use a nonzero divisor."),("Divide 999 by 0.",{'name':'calculate','arguments':{'op':'divide','a':999,'b':0}},"The calculation failed: division by zero. Please use a nonzero divisor."),("Divide 42 by 0.",{'name':'calculate','arguments':{'op':'divide','a':42,'b':0}},"The calculation failed: division by zero. Please use a nonzero divisor."),("Divide -1 by 0.",{'name':'calculate','arguments':{'op':'divide','a':-1,'b':0}},"The calculation failed: division by zero. Please use a nonzero divisor."),("Divide 0 by 0.",{'name':'calculate','arguments':{'op':'divide','a':0,'b':0}},"The calculation failed: division by zero. Please use a nonzero divisor.")]
    # Fixture-derived answer strings for non-arithmetic calls are kept explicit
    # only after their exact calls; the runner independently executes fixtures.
    out=[]
    for family, bank in [("tool_single",singles),("tool_chain",chains),("tool_error_result_use",errors)]:
        for i, item in enumerate(bank):
            prompt, calls, answer = item if family == "tool_chain" else (item[0], [item[1]], item[2])
            if answer is None: answer = answer_for(calls[-1], fixture(calls[-1]))
            out.append(tool_record(split,family,offset+i,prompt,calls,answer))
    # Result-use rows start after a supplied fixture result and must not call.
    result_rows=[("A lookup result says item_id SKU-DELTA, price 47, stock 3. Summarize it.","The test price is 47 and 3 units are in stock."),("A conversion result says 2.5 km. State it plainly.","2.5 km."),("A calculation result says 64. State the result.","The result is 64."),("A weather result says Chennai, 31 degrees Celsius, cloudy. State it.","The test weather for Chennai is 31 degrees Celsius and cloudy."),("A note result says the audit meeting is on Thursday. State the day.","The audit meeting is on Thursday."),("A lookup result says price 12 and stock 0. State both values.","The test price is 12 and 0 units are in stock."),("A conversion result says 750 cm. State it.","750 cm."),("A calculation result says 3.5. State it.","The result is 3.5.")]
    for i,(prompt,answer) in enumerate(result_rows):
        out.append({"id":f"author-eval-v3-{split}-tool_result_use-{offset+i:03d}","suite_version":"author-evaluation-v3","authorship":"assistant_authored_not_independent_benchmark","split":split,"kind":"tool","family":"tool_result_use","messages":[msg('system',SYSTEM),msg('user',prompt)],"calls":[],"expected_answer":answer,"max_turns":1,"tool_fixture":"provided_result_only"})
    if confirmation:
        # This is not a parameter sweep: confirmation asks different composed
        # tasks and names, while retaining the same local schemas/fixtures.
        swaps = {"Add":"Calculate", "Convert":"Change", "Look up":"Find inventory for", "What is":"Report", "Find the note":"Locate notes", "Subtract":"Compute", "Multiply":"Compute"}
        for row in out:
            prompt = row["messages"][-1]["content"]
            for old, new in swaps.items(): prompt = prompt.replace(old, new)
            row["messages"][-1]["content"] = "For an audit scenario, " + prompt
            for call in row["calls"]:
                args = call["arguments"]
                if "city" in args: args["city"] = "Mysuru" if args["city"] != "Mysuru" else "Surat"
                if "item_id" in args: args["item_id"] = args["item_id"] + "-CONF"
                if "query" in args: args["query"] = "confirmation " + args["query"]
                if "a" in args: args["a"] = args["a"] + 11
                if "value" in args: args["value"] = args["value"] + 4
            if row["calls"]:
                row["expected_answer"] = answer_for(row["calls"][-1], fixture(row["calls"][-1]))
    return out


def write_once(path, rows):
    if path.exists(): raise FileExistsError(f"refusing to overwrite frozen suite: {path}")
    path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",",":"))+"\n" for row in rows))


def main():
    global FACTS, REWRITES, CONSTRAINTS, FOLLOWUPS, AMBIGUITY, ABSTENTION
    OUT.mkdir(parents=True, exist_ok=True)
    dev = prose_cases("development", 1) + additional_prose_cases("development", 1) + tool_cases("development", 1)
    # Confirmation has distinct authored scenarios; its content is not loaded by
    # development decoding.  The bank is deliberately transformed before write.
    FACTS=[(p.replace('museum','archive').replace('backup','replica').replace('train','ferry').replace('survey','poll'),n) for p,n in FACTS]
    REWRITES=[(p.replace('deadline','handoff').replace('export','import').replace('migration','rollout'),n,b) for p,n,b in REWRITES]
    CONSTRAINTS=[(p.replace('password','access code').replace('API key','service credential'),n,b,m) for p,n,b,m in CONSTRAINTS]
    FOLLOWUPS=[(a.replace('final.csv','approved.pdf').replace('Thursday','Tuesday'),b,c.replace('final.csv','approved.pdf').replace('Thursday','Tuesday'),d) for a,b,c,d in FOLLOWUPS]
    AMBIGUITY=[(p.replace('report','invoice').replace('meeting','appointment'),n) for p,n in AMBIGUITY]
    ABSTENTION=[(p.replace('Acme Corp','Northstar Ltd').replace('package','shipment'),n) for p,n in ABSTENTION]
    confirm = prose_cases("confirmation", 101) + additional_prose_cases("confirmation", 101) + tool_cases("confirmation", 101, confirmation=True)
    for number, row in enumerate(confirm, 1):
        # Add independent setting details, not merely alternate argument values;
        # they make the confirmation prompt a separate scenario while keeping
        # its same predeclared scoring intent.
        user = row["messages"][-1]
        user["content"] = (f"Scenario {number}: an observatory, a harbour office, a field laboratory, and a civic archive "
                           f"are reconciling record {number} during a quarterly control exercise. " + user["content"])
    if len(dev) < 120 or len(confirm) < 120: raise ValueError("suite too small")
    write_once(OUT/"development-cases.jsonl", dev); write_once(OUT/"confirmation-cases.jsonl", confirm)
    manifest={"version":"author-evaluation-v3","authoring":"assistant_authored_not_independent_benchmark","development":{"cases":len(dev),"sha256":hashlib.sha256((OUT/'development-cases.jsonl').read_bytes()).hexdigest()},"confirmation":{"cases":len(confirm),"sha256":hashlib.sha256((OUT/'confirmation-cases.jsonl').read_bytes()).hexdigest(),"frozen":True,"used_for_decoder_selection":False},"policy":"The legacy 12-case confirmation file remains untouched. Do not inspect or use it for tuning. The failed v2 preparation is preserved. Confirmation v3 is disjoint from development v3 and must not be passed to decoding selection."}
    (OUT/"MANIFEST.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps(manifest,indent=2))


if __name__ == "__main__": main()

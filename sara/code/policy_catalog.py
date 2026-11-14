"""Fixed policies for the simplified English statutes distributed with SARA v1."""
import re

def AND(*xs): return ["and", *xs]
def OR(*xs): return ["or", *xs]
def NOT(x): return ["not", x]
def EQ(x, y): return ["=", x, y]
def ITE(g, x, y): return ["ite", g, x, y]
def rounded(x):
    # For nonnegative liabilities, round to the whole dollar in the hypothesis.
    return AND([">=", ["*", 2, x], ["-", ["*", 2, "AMOUNT"], 1]],
               ["<", ["*", 2, x], ["+", ["*", 2, "AMOUNT"], 1]])

CATALOG = {}
def add(section, source, rule, **fields):
    variables = {}
    for name, desc in fields.items():
        sort, meaning = desc if isinstance(desc, tuple) else ("Bool", desc)
        variables[name] = dict(type=sort, meaning=meaning)
    CATALOG[section.lower()] = dict(source=source, variables=variables, rule=rule)

def number(desc): return ("Real", desc)
def integer(desc): return ("Int", desc)

def flag(section, source, meaning):
    add(section, source, "fact", fact=meaning)

married = "Taxpayer was married at the legally relevant time in the specified tax year."
joint = "Taxpayer filed a joint return with spouse for the tax year."
survivor = "Taxpayer had surviving-spouse status for this tax year."
head = "Taxpayer had head-of-household status for this tax year."
income = number("Taxable income in dollars of the taxpayer for the year in the hypothesis.")
agi = number("Adjusted gross income of the taxpayer for the relevant year, dollars.")
year = integer("Tax year of the exemption or deduction described in the narrative.")
status_fields = dict(married=married, joint=joint, survivor=survivor, head=head)
# Dollar bases below are in cents, and rates in tenths of a percent.
schedules = {
    "a": ([36900,89150,140000,250000], [0,553500,2016500,3592850,7552850],
          OR(AND("married","joint"),"survivor"), ["married","joint","survivor"]),
    "b": ([29600,76400,127500,250000], [0,444000,1754400,3338500,7748500],
          "head", ["head"]),
    "c": ([22100,53500,115000,250000], [0,331500,1210700,3117200,7977200],
          AND(NOT("married"),NOT("survivor"),NOT("head")), ["married","survivor","head"]),
    "d": ([18450,44575,70000,125000], [0,276750,1008250,1796425,3776425],
          AND("married",NOT("joint")), ["married","joint"]),
}
requested = {"a": ["","iv","v"], "b":["","i"], "c":["","iii"], "d":["","i","ii"]}
for group,(edges,bases,status,names) in schedules.items():
    for sub in requested[group]:
        alternatives = []
        for i, roman in enumerate(("i","ii","iii","iv","v")):
            if sub and roman != sub: continue
            floor = edges[i-1] if i else 0
            tax = ["+", ["/",bases[i],100], ["/",["*",[150,280,310,360,396][i],["-","income",floor]],1000]]
            bounds = [[">","income",floor]] if i else [[">=","income",0]]
            if i < len(edges): bounds.append(["<=","income",edges[i]])
            alternatives.append(AND(*bounds,rounded(tax)))
        # Bracket-only hypotheses test the named row, full-section queries include filing status.
        rule = OR(*alternatives)
        fields = dict(income=income)
        if not sub:
            fields.update({name:status_fields[name] for name in names}); rule=AND(status,rule)
        add(f"1({group})"+(f"({sub})" if sub else ""), "tax determined in accordance with the following",rule,**fields)

flag("7703(b)(2)","such individual furnishes over one-half","Named taxpayer furnished more than half of this home's maintenance costs in the specified year.")
add("63(f)(1)(A)","if he has attained age 65",[">=",["-","YEAR","birth"],65],birth=integer("Birth year of the taxpayer named in the question."))
flag("63(c)(2)(A)(i)","a joint return",joint)
flag("63(c)(2)(A)(ii)","a surviving spouse",survivor)
flag("2(b)(3)(A)","he is a nonresident alien","Named taxpayer was a nonresident alien at any point in the tax year.")
flag("63(c)(6)(B)","a nonresident alien individual","Taxpayer was a nonresident alien in the tax year.")
add("63(c)(6)(D)","an estate or trust",OR("estate","trust","partnership"),estate="Entity was an estate in the specified year.",trust="Entity was a trust, including a common trust fund, in the specified year.",partnership="Entity was a partnership in the specified year.")
add("63(f)(2)(B)","if the spouse is blind",AND("blind","exemption"),blind="Spouse of named taxpayer was blind at year end (or at death if spouse died in that year).",exemption="Spousal exemption under 151(b) was allowable for that spouse and year.")
add("63(b)","does not elect to itemize",AND(NOT("itemizes"),EQ(["-","agi","standard","personal"],"AMOUNT")),itemizes="Taxpayer elected itemized deductions.",agi=agi,standard=number("Standard deduction dollars for that taxpayer/year."),personal=number("Total personal exemption deductions under section 151 in dollars."))
add("63(c)(7)(i)",'by substituting "$18,000"',AND([">","YEAR",2017],["<","YEAR",2026],EQ("AMOUNT",18000)))
add("3301","6 percent of the total wages",AND("employer",rounded(["/",["*",6,"wages"],100])),employer="Payer has employer status under 3306(a) for the year queried.",wages=number("Total wages paid for covered employment by named employer in the year queried, dollars."))
for sec,source,meaning in [
 ("3306(c)(6)","United States Government","Employer for the specified service was the US federal government."),
 ("3306(c)(7)","political subdivision thereof","Employer for the specified service was a US state or its political subdivision."),
 ("3306(c)(11)","employ of a foreign government","Employer for the service was a foreign government, including its consular or diplomatic service."),
 ("3306(c)(16)","international organization","Employer for the service was an international organization."),
 ("3306(b)(2)(C)","(C) death","Purpose of the specific plan or fund payment in the hypothesis was to provide a death benefit."),
 ("2(b)(1)(A)(i)(I)","is married at the close","The named child was married at the close of the specified tax year."),
 ("2(b)(1)(A)(i)(II)","by reason of section 152(b)(2)","Child made a joint return with spouse for the taxable year in question, giving rise to the section 152(b)(2) exclusion."),
 ("152(d)(1)(D)","not a qualifying child",""),]:
    if meaning: flag(sec,source,meaning)
add("152(d)(1)(D)","not a qualifying child",NOT("child"),child="Individual was a qualifying child of any taxpayer for the relevant tax year.")
for sec in ("152(c)(2)(A)","152(d)(2)(A)"):
    add(sec,"descendant of a child" if "(d)" in sec else "descendant of such a child",OR("child","desc"),child="First named person is a child of the second person.",desc="First person is a further descendant of a child of the second person.")
add("152(d)(2)(C)","ancestor of either",OR("parent","ancestor"),parent="First person is a parent of the second.",ancestor="First person is an ancestor of a parent of the second.")
flag("152(d)(2)(G)","or sister-in-law","First person is son/daughter/father/mother/brother/sister-in-law of the second person in the relevant period.")
add("152(d)(2)(H)","member of the taxpayer's household",AND(NOT("spouse"),"resides","member"),spouse="First person was spouse of second at any time during tax year.",resides="Both had same principal abode for tax year.",member="First person was member of second person's household for tax year.")
add("152(a)","a qualifying relative",OR("child","relative"),child="Individual is a qualifying child of the taxpayer for that year (including stated section 152(c)(1) status).",relative="Individual is a qualifying relative of the taxpayer in that year under 152(d).")
add("2(b)(1)(A)(ii)","any other person who is a dependent",AND("dependent","deduction"),dependent="Named person is a dependent of the taxpayer for this year.",deduction="Taxpayer entitled to a section 151 deduction for this person for the year.")
add("2(b)(1)(A)(i)","but not if such child",AND("child",NOT(AND("married_child","joint_child"))),child="Named person was taxpayer's qualifying child under 152(c).",married_child="Child married at close of taxpayer's tax year.",joint_child="Child made joint spousal return triggering 152(b)(2) exclusion.")
add("2(a)(1)(B)","who maintains as his home a household",AND("cost","home","child","dependent","deduction"),cost="Taxpayer furnished more than half of household maintenance costs.",home="Home was taxpayer's home and dependent's principal abode as a household member throughout tax year.",child="Dependent is taxpayer's son, stepson, daughter or stepdaughter.",dependent="Person was a dependent of this taxpayer in the year.",deduction="Taxpayer entitled to section 151 deduction for dependent in year.")
flag("7703(a)(1)","as of the close of his taxable year","Taxpayer was married at year end, or immediately before spouse's death if spouse died within that year.")
add("3306(c)(10)(B)","patient of such hospital",AND("hospital","patient"),hospital="Service performed for hospital employer.",patient="Worker was a patient of same hospital when services were performed.")
add("3306(c)(B)","performed outside the United States",AND("abroad",NOT("excluded_country"),"citizen","employer"),abroad="Service was performed outside USA.",excluded_country="Service performed in contiguous country with US unemployment-compensation agreement.",citizen="Employee was US citizen.",employer="Employer was an American employer.")
add("3306(c)(1)(B)","alien admitted to the United States",AND("agricultural",NOT("admitted")),agricultural="Labor in question was agricultural.",admitted="Worker was an alien admitted to US to perform agricultural labor under the specified immigration provisions.")
add("3306(a)(1)(B)","each day being in a different calendar week",OR([">=","weeks",10],[">=","prior",10]),weeks=integer("Distinct calendar weeks with at least one employee on a day of covered non-domestic employment in queried year."),prior=integer("Corresponding distinct weeks for preceding calendar year."))
add("3306(a)(3)","paid wages in cash of $1,000 or more",OR([">=","cash",1000],[">=","prior",1000]),cash=number("Cash wages payer paid for domestic services in private home, local college club or local fraternity/sorority chapter in queried year."),prior=number("Same payer's cash wages for such domestic services in preceding year."))
active=OR(["<","YEAR",2018],[">","YEAR",2025])
add("68(b)(1)(B)","$275,000 in the case",AND(active,"head",EQ("AMOUNT",275000)),head=head)
add("68(b)(1)(C)","$250,000 in the case",AND(active,NOT("married"),NOT("survivor"),NOT("head"),"OPTIONAL_250K"),married=married,survivor=survivor,head=head)
add("68(a)(2)","80 percent of the amount",AND(active,EQ(["/",["*",80,"itemized"],100],"AMOUNT")),itemized=number("Total otherwise allowable itemized deductions for year, before section 68 reduction."))
add("151(d)(1)",'means $2,000',EQ("AMOUNT",2000))
add("151(d)(5)",'means zero',AND([">=","year",2018],["<=","year",2025],EQ("AMOUNT",0)),year=year)
# Invert the ceiling in the phaseout: band k corresponds to (k-1)*step < excess <= k*step.
threshold=ITE(OR("joint","survivor"),300000,ITE("head",275000,ITE("separate",150000,250000)))
excess=["-","agi",threshold];step=ITE("separate",1250,2500)
bands=["/",["-",2000,"AMOUNT"],40]
add("151(d)(3)(A)","2 percentage points for each",AND([">",excess,0],OR(AND(EQ("AMOUNT",0),[">",excess,["*",49,step]]),AND(["INTEGRAL_BAND"],[">","AMOUNT",0],["<","AMOUNT",2000],[">",excess,["*",["-",bands,1],step]],["<=",excess,["*",bands,step]]))),agi=agi,joint=joint,survivor=survivor,head=head,separate="Taxpayer married filing separately.")

import React, { useState } from 'react';
import { 
  BookOpen, 
  Search, 
  Copy, 
  Check, 
  ExternalLink, 
  ShieldCheck, 
  CheckCircle2, 
  XCircle, 
  Flame, 
  Building2, 
  Briefcase, 
  Cpu, 
  Anchor, 
  Clock, 
  Scale, 
  Sparkles
} from 'lucide-react';


export default function SearchPlaybook() {
  const [activeCategory, setActiveCategory] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [copiedId, setCopiedId] = useState(null);
  const [activeTab, setActiveTab] = useState('directory'); // 'directory', 'search_bank', 'routines', 'scoring', 'qc'

  // Interactive Scoring Calculator State
  const [scoreFactors, setScoreFactors] = useState({
    fleet_range: true,
    active_carrier: true,
    decision_maker: true,
    equipment_match: true,
    usable_contact: true,
    intent_signal: false,
    tech_signal: false
  });

  const handleCopy = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const calculateInteractiveScore = () => {
    let score = 0;
    if (scoreFactors.fleet_range) score += 2;
    if (scoreFactors.active_carrier) score += 2;
    if (scoreFactors.decision_maker) score += 2;
    if (scoreFactors.equipment_match) score += 1;
    if (scoreFactors.usable_contact) score += 1;
    if (scoreFactors.intent_signal) score += 1;
    if (scoreFactors.tech_signal) score += 1;
    return score;
  };

  const currentScore = calculateInteractiveScore();
  const currentTier = currentScore >= 8 ? 'A' : (currentScore >= 5 ? 'B' : 'C');

  // Master 41+ Lead Generation Methods & Websites Library
  const searchMethods = [
    // 1-3: Federal & Safety
    {
      id: 1,
      name: "FMCSA / USDOT Carrier Census Snapshot",
      category: "federal",
      type: "Discovery + Verification",
      url: "https://usdotlookup.com/",
      why: "Core authoritative census registry for finding and verifying active U.S. interstate motor carriers, USDOT numbers, fleet size, and safety history.",
      searchTerms: ["Company Name", "USDOT Number", "State/City + Trucking", "Active Carrier Filter"],
      procedure: "1. Search USDOT/name. 2. Verify operating status = ACTIVE. 3. Record power units & driver count. 4. Continue to website for decision-maker.",
      keepWhen: "Carrier is ACTIVE, authorized for hire, and fits 2-10 truck fleet ICP.",
      recordFields: ["Company Name", "USDOT", "City/State", "Fleet Size", "Cargo/Equipment", "Website", "Verification Date"]
    },
    {
      id: 2,
      name: "FMCSA Licensing & Operating Authority Lookup",
      category: "federal",
      type: "Authority & Insurance Verification",
      url: "https://usdotlookup.com/",
      why: "Public federal registry lookup for operating authority (Common / Contract / Broker) and active $750k+ BIPD and Cargo insurance policy filings.",
      searchTerms: ["USDOT Number", "Docket Number (MC-)", "Legal Name + State", "DBA Name + State"],
      procedure: "1. Enter USDOT or MC number. 2. Verify Active Common/Contract authority. 3. Check Form BMC-91X insurance underwriter.",
      keepWhen: "Authority is ACTIVE and insurance policy is in good standing.",
      recordFields: ["Legal/DBA Name", "MC/Docket #", "USDOT", "Insurance Policy # & Underwriter", "Authority Status"]
    },
    {
      id: 3,
      name: "FMCSA Company Safety Records & SMS",
      category: "federal",
      type: "Verification & Safety Support",
      url: "https://www.fmcsa.dot.gov/safety/company-safety-records",
      why: "Secondary validation layer to check carrier safety compliance, out-of-service rates, and inspection history.",
      searchTerms: ["Company Name", "USDOT", "SAFER Snapshot", "Safety and Fitness (SMS)"],
      procedure: "1. Open SMS lookup. 2. Confirm zero fatal violations or severe out-of-service orders.",
      keepWhen: "Information confirms safe operating carrier with no active shut-down orders.",
      recordFields: ["Safety Rating", "Inspection Count", "Out-of-Service Rate", "Verification Date"]
    },
    // 4-5: Communities
    {
      id: 4,
      name: "Facebook Trucking Communities",
      category: "social",
      type: "Community Discovery",
      url: "https://www.facebook.com/",
      why: "Discover real small fleet owners and owner-operators participating in active freight and dispatch discussions.",
      searchTerms: ["Owner Operators USA", "Owner operator Texas", "Small fleet owners trucking", "Dispatch service trucking", "Hotshot trucking USA"],
      procedure: "1. Search Groups and public posts. 2. Identify verifiable business names. 3. Verify company externally via SAFER.",
      keepWhen: "Identified company can be independently verified on SAFER with a real business presence.",
      recordFields: ["Company Name", "Group/Post URL", "Company Website", "Signal Context"]
    },
    {
      id: 5,
      name: "Reddit Trucking Communities",
      category: "social",
      type: "Community Discovery",
      url: "https://www.reddit.com/",
      why: "Surface public discussions where carriers and small fleets express operational needs, rate inquiries, or dispatch challenges.",
      searchTerms: ["r/Truckers", "r/FreightBrokers", "dispatcher", "dispatch service", "finding loads", "owner operator small fleet"],
      procedure: "1. Search subreddits for operational pain points. 2. Extract company names when mentioned publicly. 3. Never lead-capture anonymous accounts without external business identity.",
      keepWhen: "Company is independently verifiable via FMCSA / web.",
      recordFields: ["Company Name", "Thread URL", "Public Need Signal", "Verification Source"]
    },
    // 6-8: B2B & Enrichment
    {
      id: 6,
      name: "LinkedIn Search & Sales Navigator",
      category: "b2b",
      type: "Company & Decision-Maker Discovery",
      url: "https://www.linkedin.com/",
      why: "Locate executive decision-makers (Owner, Founder, President, Fleet Manager, Operations Manager) with verified career profiles.",
      searchTerms: ['"Owner" "trucking company" "Texas"', '"Founder" "trucking" Florida', '"Fleet Manager" trucking', '"Operations Manager" carrier'],
      procedure: "1. Search company name or executive title + geography. 2. Confirm connection to target carrier. 3. Extract verified profile link.",
      keepWhen: "Decision-maker is clearly verified and currently active with the carrier.",
      recordFields: ["Decision Maker Name", "Job Title", "LinkedIn URL", "Company URL", "Business Email"]
    },
    {
      id: 7,
      name: "Apollo.io B2B Intelligence",
      category: "b2b",
      type: "B2B Discovery + Enrichment",
      url: "https://www.apollo.io/",
      why: "Build ultra-targeted company and executive contact lists with firmographic filters, headcount (1-10), and direct phone/email data.",
      searchTerms: ["Industry: Trucking / Transportation", "Titles: Owner, President, Founder, Fleet Director", "Headcount: 1-10", "Location: US States"],
      procedure: "1. Apply location & industry filters. 2. Filter 1-10 employees. 3. Export verified email & direct dial contacts.",
      keepWhen: "Company and contact match ICP and pass domain deliverability check.",
      recordFields: ["Company Name", "Decision Maker", "Title", "Corporate Email", "Direct Phone", "Headcount"]
    },
    {
      id: 8,
      name: "Lusha B2B Enrichment",
      category: "b2b",
      type: "B2B Contact Enrichment",
      url: "https://www.lusha.com/",
      why: "Enrich high-accuracy mobile direct dials and verified work emails for trucking owners and fleet executives.",
      searchTerms: ["Transportation / Trucking", "Seniority: Owner, Partner, CXO, Director", "Company Size: 1-10", "Location: United States"],
      procedure: "1. Input target company domain or executive name. 2. Reveal verified phone & email under compliant plan.",
      keepWhen: "Contact belongs to target business and role matches decision-maker standard.",
      recordFields: ["Company", "Person", "Title", "Verified Phone", "Verified Email", "Enrichment Date"]
    },
    // 9: Carrier Qualification
    {
      id: 9,
      name: "Carrier411",
      category: "commercial",
      type: "Carrier Qualification & Risk Audit",
      url: "https://www.carrier411.com/",
      why: "Industry-standard risk intelligence platform for checking carrier safety scores, certificate compliance, and FreightGuard reports.",
      searchTerms: ["Company Name", "USDOT Number", "MC/Docket", "Insurance Certificate / Safety Alert Search"],
      procedure: "1. Lookup carrier. 2. Confirm active certificates and zero active freight guard complaints.",
      keepWhen: "Carrier has clean qualification context and active operating authority.",
      recordFields: ["Company Name", "USDOT", "FreightGuard Status", "Certificate Compliance", "Verification Date"]
    },
    // 10-11: Search & Maps
    {
      id: 10,
      name: "Google Maps / Business Profiles",
      category: "local",
      type: "Local Company Discovery",
      url: "https://maps.google.com/",
      why: "Find brick-and-mortar local carrier yards, verified business phone numbers, websites, and operational headquarters.",
      searchTerms: ['"trucking company" Dallas TX', '"dry van carrier" Atlanta GA', '"flatbed trucking" Houston', '"reefer carrier" Chicago IL'],
      procedure: "1. Search metro + carrier niche. 2. Open business profile. 3. Record business phone, website, and physical yard address.",
      keepWhen: "Active local trucking company with verifiable physical address and website.",
      recordFields: ["Company Name", "City/State", "Yard Address", "Phone", "Website", "Google Maps URL"]
    },
    {
      id: 11,
      name: "Google Advanced Boolean Search",
      category: "local",
      type: "Open-Web Deep Discovery",
      url: "https://www.google.com/",
      why: "Uncover unlisted carriers, regional fleet websites, and high-intent footprints that standard directories miss.",
      searchTerms: ['"trucking company" "Texas" "owner"', '"dry van carrier" "Georgia" "contact us"', '"trucking LLC" "hiring dispatcher"', 'site:*.com "USDOT" "fleet" "Dallas"'],
      procedure: "1. Execute quoted phrases with geographic operators. 2. Extract underlying company domain. 3. Cross-reference SAFER.",
      keepWhen: "Company is verified via SAFER and website contains usable contact details.",
      recordFields: ["Company Name", "Query String", "Source URL", "Decision Maker", "Contact Info"]
    },
    // 12-13: Job Boards
    {
      id: 12,
      name: "Indeed Job Search",
      category: "intent",
      type: "Hiring & Operational Intent",
      url: "https://www.indeed.com/",
      why: "Identify carriers actively experiencing dispatch bottlenecks, fleet growth, or hiring transportation staff.",
      searchTerms: ['"dispatcher" trucking', '"dispatch manager" carrier', '"fleet manager" trucking', '"transportation coordinator" freight'],
      procedure: "1. Search role + state. 2. Identify hiring carrier entity. 3. Tag lead with 'Hiring Intent Signal'.",
      keepWhen: "Carrier matches ICP and has an active hiring requisition.",
      recordFields: ["Company Name", "Job Title Listed", "Job Posting URL", "Posting Date", "Decision Maker"]
    },
    {
      id: 13,
      name: "ZipRecruiter Job Marketplace",
      category: "intent",
      type: "Hiring & Growth Intent",
      url: "https://www.ziprecruiter.com/find-a-job",
      why: "Alternative high-intent hiring feed to capture small fleets advertising driver and dispatch positions.",
      searchTerms: ['"dispatcher" "trucking company"', '"fleet manager" transport', '"logistics coordinator" carrier'],
      procedure: "1. Run role queries by geography. 2. Extract employer name. 3. Qualify carrier fleet size via SAFER.",
      keepWhen: "Verified carrier with active operational expansion signal.",
      recordFields: ["Company Name", "Hiring Requisition", "Location", "Source URL", "Decision Maker"]
    },
    // 14-17: Directories & Associations
    {
      id: 14,
      name: "ATA State Trucking Associations",
      category: "commercial",
      type: "State Industry Directories",
      url: "https://www.trucking.org/ata-sites",
      why: "Access verified state association member directories (TXTA, FTA, GMTA, ITA, OTA, PMTA, CTA) representing established carriers.",
      searchTerms: ["Texas trucking association member directory", "Florida trucking association carriers", "Georgia motor trucking directory"],
      procedure: "1. Navigate to state association. 2. Browse member carrier listings. 3. Cross-reference fleet size in SAFER.",
      keepWhen: "Member carrier fits 2-10 truck fleet ICP.",
      recordFields: ["State Association", "Company Name", "Website", "Executive Contact", "Member Status"]
    },
    {
      id: 15,
      name: "Chamber of Commerce Directories",
      category: "commercial",
      type: "Local Business Networks",
      url: "https://www.chamberofcommerce.com/",
      why: "Discover established regional logistics and hauling businesses enrolled in municipal business alliances.",
      searchTerms: ["Dallas Chamber trucking members", "Houston Chamber transportation", "Atlanta Chamber logistics"],
      procedure: "1. Search city + chamber + trucking. 2. Extract company and phone. 3. Verify carrier status in SAFER.",
      keepWhen: "Verified commercial motor carrier with local standing.",
      recordFields: ["Company Name", "City/State", "Chamber Directory URL", "Phone", "Website"]
    },
    {
      id: 16,
      name: "Better Business Bureau (BBB)",
      category: "commercial",
      type: "Commercial Business Check",
      url: "https://www.bbb.org/search/",
      why: "Verify business registration, physical headquarters, operating years, and leadership names.",
      searchTerms: ["Trucking", "Freight Transportation", "Motor Carrier", "City + Trucking"],
      procedure: "1. Search company name or category + city. 2. Extract principal officers and phone. 3. Validate with FMCSA.",
      keepWhen: "Company profile confirms legitimate trucking entity and leadership.",
      recordFields: ["Company Name", "BBB Rating", "Principal Officer", "Phone", "Location"]
    },
    {
      id: 17,
      name: "Yellow Pages Commercial Directory",
      category: "commercial",
      type: "Local Directory Discovery",
      url: "https://www.yellowpages.com/",
      why: "Surface legacy and independent small fleet carriers that lack heavy digital advertising footprints.",
      searchTerms: ["Trucking + City/State", "Freight Hauling + State", "Motor Carrier + City"],
      procedure: "1. Search target metro. 2. Extract candidate listings. 3. Verify carrier status and fleet size via SAFER.",
      keepWhen: "Relevant business with verifiable active USDOT.",
      recordFields: ["Company Name", "Category", "City/State", "Phone", "Website"]
    },
    // 18-20: Federal Procurement
    {
      id: 18,
      name: "SAM.gov Contract Opportunities",
      category: "federal",
      type: "Federal Procurement Discovery",
      url: "https://sam.gov/opportunities",
      why: "Find motor carriers bidding on federal transportation, disaster relief (FEMA), and freight movement contracts.",
      searchTerms: ['"trucking services"', '"freight transportation"', '"hauling services"', '"motor carrier"'],
      procedure: "1. Search transportation solicitations. 2. Identify participating carriers and vendors. 3. Verify carrier fit.",
      keepWhen: "Verified carrier with active federal procurement readiness.",
      recordFields: ["Company Name", "Opportunity Title", "Notice ID", "Decision Maker", "Source URL"]
    },
    {
      id: 19,
      name: "SAM.gov Contract Award Data",
      category: "federal",
      type: "Federal Award Intelligence",
      url: "https://sam.gov/contracting",
      why: "Discover carriers that have won government freight awards and have verified funding and operational volume.",
      searchTerms: ['Contract Awards + "trucking"', '"freight hauling" award', '"small business transportation"'],
      procedure: "1. Search contract awards. 2. Extract awardee entity. 3. Confirm carrier fleet size in SAFER.",
      keepWhen: "Awardee matches 2-10 fleet target.",
      recordFields: ["Awardee Name", "Award ID", "Award Amount/Date", "Decision Maker", "Website"]
    },
    {
      id: 20,
      name: "USAspending.gov",
      category: "federal",
      type: "Federal Spending Discovery",
      url: "https://www.usaspending.gov/",
      why: "Track federal transportation grants, disaster logistics payouts, and prime carrier recipient records.",
      searchTerms: ["trucking recipient", "freight hauling grant", "transportation delivery award"],
      procedure: "1. Run keyword search in Award Search. 2. Filter transportation recipients. 3. Enrich carrier contact details.",
      keepWhen: "Recipient is an active commercial motor carrier.",
      recordFields: ["Recipient Name", "Award Context", "Fiscal Year", "Contact Info", "USDOT"]
    },
    // 21-24: Tech Ecosystems
    {
      id: 21,
      name: "G2 Trucking & TMS Reviews",
      category: "tech",
      type: "Technology Ecosystem Discovery",
      url: "https://www.g2.com/categories/trucking",
      why: "Extract publicly named carrier customer case studies and reviews across TMS, ELD, and dispatch software.",
      searchTerms: ["Trucking software reviews", "Small business trucking TMS", "Dispatch management software", "Fleet tracking"],
      procedure: "1. Browse software category. 2. Identify verified carrier reviewers. 3. Research carrier decision-makers.",
      keepWhen: "Named carrier is verified on SAFER with supported fleet size.",
      recordFields: ["Company Name", "Software Reviewed", "Review URL", "Decision Maker"]
    },
    {
      id: 22,
      name: "Software Advice — Transportation Management",
      category: "tech",
      type: "Tech Ecosystem Footprints",
      url: "https://www.softwareadvice.com/product/505782-Transportation-Management-Software/",
      why: "Discover carriers evaluating or utilizing modern dispatch and fleet management technologies.",
      searchTerms: ["Transportation Management Software", "Trucking TMS", "Dispatch software customer stories"],
      procedure: "1. Review provider customer references. 2. Extract named carriers. 3. Validate fleet size in SAFER.",
      keepWhen: "Carrier is independently verified.",
      recordFields: ["Company Name", "Tech Signal", "Source URL", "Decision Maker"]
    },
    {
      id: 23,
      name: "BuiltWith Technographic Search",
      category: "tech",
      type: "Technographic Intelligence",
      url: "https://builtwith.com/",
      why: "Find carrier websites running specific dispatch portals, ELD login widgets, or freight booking widgets.",
      searchTerms: ["Technology name (e.g. McLeod, Samsara, Motive)", "Keyword: 'USDOT'", "Country: United States"],
      procedure: "1. Query website technology. 2. Filter US domains. 3. Qualify carrier profiles.",
      keepWhen: "Domain belongs to active motor carrier.",
      recordFields: ["Domain", "Company Name", "Detected Technology", "State", "Contact"]
    },
    {
      id: 24,
      name: "Wappalyzer Tech Lookup",
      category: "tech",
      type: "Technographic Enrichment",
      url: "https://www.wappalyzer.com/lookup/",
      why: "Inspect carrier websites for analytics, CRM, portal integrations, and technology sophistication.",
      searchTerms: ["Company Website URL", "Transportation tech category"],
      procedure: "1. Input carrier domain. 2. Extract tech stack. 3. Use tech stack as prioritization context.",
      keepWhen: "Carrier fits ICP with documented tech stack.",
      recordFields: ["Website", "Tech Stack", "Company Name", "Enrichment Date"]
    },
    // 25-27: Industry News
    {
      id: 25,
      name: "FreightWaves Carrier News",
      category: "news",
      type: "Industry Growth Discovery",
      url: "https://www.freightwaves.com/news/tag/trucking-carriers",
      why: "Identify carriers announcing new truck orders, regional terminal openings, lane expansions, or funding.",
      searchTerms: ['"carrier expansion"', '"trucking company" "new terminal"', '"carrier" "new trucks"', '"small carrier growth"'],
      procedure: "1. Search carrier news articles. 2. Extract named carrier entities. 3. Verify company in SAFER.",
      keepWhen: "Carrier is expanding and fits 2-10 fleet size target.",
      recordFields: ["Company Name", "Article URL", "Expansion Event", "Date", "Decision Maker"]
    },
    {
      id: 26,
      name: "Transport Topics For-Hire News",
      category: "news",
      type: "Commercial News Intelligence",
      url: "https://www.ttnews.com/for-hire",
      why: "Track commercial for-hire motor carriers in regional news, equipment acquisitions, and fleet developments.",
      searchTerms: ['"for-hire carrier" growth', '"trucking company" expansion', '"new facility" carrier'],
      procedure: "1. Scan recent news stories. 2. Extract carrier name. 3. Verify fleet size & authority in SAFER.",
      keepWhen: "Carrier is verified with documented growth context.",
      recordFields: ["Company Name", "News Article", "Event Context", "Decision Maker"]
    },
    {
      id: 27,
      name: "Google News Business Search",
      category: "news",
      type: "Business Event Discovery",
      url: "https://news.google.com/",
      why: "Surface local news articles covering small trucking companies expanding operations, buying trucks, or adding routes.",
      searchTerms: ['"trucking company" "expanding" Texas', '"carrier" "adds trucks" Florida', '"freight company" "new facility"'],
      procedure: "1. Execute event query with target state. 2. Extract company. 3. Qualify as prioritized lead.",
      keepWhen: "Verified carrier with documented growth trigger.",
      recordFields: ["Company Name", "News Trigger", "Article Date", "Decision Maker", "Source URL"]
    },
    // 28-30: Events & Media
    {
      id: 28,
      name: "Trade Show & Conference Exhibitors",
      category: "events",
      type: "Event-Based Discovery",
      url: "https://www.google.com/",
      why: "Find carriers investing in growth through industry trade show attendance (Mid-America Trucking Show, GATS, ATA Summit).",
      searchTerms: ['"MATS 2026" exhibitor list', '"trucking conference" sponsors', '"transportation expo" attendees'],
      procedure: "1. Open exhibitor directory. 2. Filter motor carriers from hardware vendors. 3. Verify carrier in SAFER.",
      keepWhen: "Carrier matches ICP with verified event presence.",
      recordFields: ["Company Name", "Event Name", "Exhibitor Page", "Decision Maker"]
    },
    {
      id: 29,
      name: "YouTube & Trucking Podcasts",
      category: "social",
      type: "Content-Based Discovery",
      url: "https://www.youtube.com/",
      why: "Discover outspoken owner-operators and small fleet owners featured in interviews and business podcasts.",
      searchTerms: ['"trucking company owner interview"', '"fleet owner" podcast', '"owner operator business" 2026'],
      procedure: "1. Watch/search interviews. 2. Extract publicly named fleet. 3. Verify on SAFER and find contact.",
      keepWhen: "Named company can be independently verified on SAFER.",
      recordFields: ["Company Name", "Video/Podcast URL", "Owner Name", "Source"]
    },
    {
      id: 30,
      name: "Factoring / Insurance / ELD Case Studies",
      category: "tech",
      type: "Case-Study Intelligence",
      url: "https://www.google.com/",
      why: "Find small carriers highlighted in case studies by factoring firms (Apex, OTR, RTS) and ELD providers (Motive, Samsara).",
      searchTerms: ['"carrier success story" factoring', '"trucking customer spotlight" insurance', '"fleet case study" ELD'],
      procedure: "1. Search case studies. 2. Extract named carrier. 3. Verify carrier size and active authority.",
      keepWhen: "Carrier is verified with technology adoption signal.",
      recordFields: ["Company Name", "Provider Partner", "Case Study URL", "Decision Maker"]
    },
    // 31-36: Verticals & Geographies
    {
      id: 31,
      name: "State Business Registries (Secretary of State)",
      category: "federal",
      type: "State Corporate Entity Search",
      url: "https://www.google.com/",
      why: "Search official state Secretary of State databases (Texas SOSDirect, Florida Sunbiz, Georgia Corporations) for registered logistics LLCs.",
      searchTerms: ["Texas SOS business search trucking", "Florida Sunbiz search transport", "Georgia corporations freight LLC"],
      procedure: "1. Open official state registry. 2. Search trucking keywords. 3. Verify carrier operational status in SAFER.",
      keepWhen: "Active state LLC with matching active SAFER carrier snapshot.",
      recordFields: ["Legal Name", "State Filing ID", "Registered Agent", "Formation Date", "USDOT"]
    },
    {
      id: 32,
      name: "Port & Drayage Gateways",
      category: "verticals",
      type: "Specialized Drayage Discovery",
      url: "https://www.google.com/",
      why: "Find specialized container and drayage carriers operating around major intermodal sea ports.",
      searchTerms: ['"drayage carriers" "Los Angeles"', '"container trucking" Houston port', '"drayage companies" Savannah port', '"intermodal carrier" Newark NJ'],
      procedure: "1. Target specific port gateway. 2. Identify local drayage fleets. 3. Verify TWIC/intermodal readiness & fleet size.",
      keepWhen: "Active drayage motor carrier matching target fleet size.",
      recordFields: ["Company Name", "Port Gateway", "Equipment (Drayage/Chassis)", "Contact", "Source"]
    },
    {
      id: 33,
      name: "Warehouse & Inland Logistics Parks",
      category: "verticals",
      type: "Geographic Cluster Discovery",
      url: "https://www.google.com/",
      why: "Target carriers clustered around major distribution epicenters (Dallas Inland Port, Chicago Logistics Center, Atlanta I-85 corridor).",
      searchTerms: ['trucking companies near "Dallas Inland Port"', 'carriers near "Chicago logistics hub"', 'trucking "Lehigh Valley logistics"'],
      procedure: "1. Target industrial park hub. 2. Surface carriers operating locally. 3. Cross-reference SAFER.",
      keepWhen: "Carrier operates within major freight corridor hub.",
      recordFields: ["Company Name", "Logistics Hub", "City/State", "Decision Maker", "Website"]
    },
    {
      id: 34,
      name: "Equipment-Specific Prospecting",
      category: "verticals",
      type: "Equipment Vertical Segmentation",
      url: "https://www.google.com/",
      why: "Build specialized high-yield carrier batches segmented strictly by equipment type.",
      searchTerms: ['"dry van carrier" Texas', '"reefer carrier" Georgia', '"flatbed trucking" Ohio', '"hotshot trucking" Florida', '"box truck carrier" Illinois'],
      procedure: "1. Search equipment + state. 2. Confirm equipment on website/SAFER. 3. Tag equipment category in lead record.",
      keepWhen: "Equipment category is explicitly supported by official record.",
      recordFields: ["Company Name", "Equipment Type", "Fleet Count", "Decision Maker", "Source"]
    },
    {
      id: 35,
      name: "Geographic Cluster Campaigns",
      category: "verticals",
      type: "Geographic Clustering",
      url: "https://maps.google.com/",
      why: "Execute high-density campaigns by concentrating on specific freight triangles (Texas Triangle, Southeast Core, Midwest Belt).",
      searchTerms: ["trucking companies Dallas TX", "trucking companies Houston TX", "trucking companies Atlanta GA", "trucking companies Chicago IL"],
      procedure: "1. Focus on one metro area. 2. Batch 20-30 prospects. 3. Complete verification and handoff.",
      keepWhen: "Carrier is located within target geographic market.",
      recordFields: ["City/State", "Company Name", "USDOT", "Source", "Score"]
    },
    {
      id: 36,
      name: "Lane & Freight-Corridor Mapping",
      category: "verticals",
      type: "Operational Corridor Targeting",
      url: "https://www.google.com/",
      why: "Organize carriers around documented interstate freight corridors (I-10, I-35, I-80, I-95, I-75).",
      searchTerms: ['"Texas to California" carrier', '"Southeast dry van" lanes', '"Midwest to Florida" freight carrier'],
      procedure: "1. Query documented lane routes. 2. Verify service regions from carrier website. 3. Record lane context.",
      keepWhen: "Lane/region information is documented without guessing.",
      recordFields: ["Company Name", "Documented Lanes", "Equipment", "Decision Maker", "Source"]
    },
    // 37-38: High-Intent
    {
      id: 37,
      name: "Public Intent & Dispatch Requests",
      category: "intent",
      type: "High-Intent Dispatch Discovery",
      url: "https://www.google.com/",
      why: "Capture carriers actively posting public requests seeking dispatchers, load coverage, or rate negotiations.",
      searchTerms: ['"looking for dispatcher" trucking', '"need a dispatcher" trucking', '"need dispatch service" carrier', '"dispatch service needed" freight'],
      procedure: "1. Search public social/job/forum signals. 2. Identify underlying company. 3. Verify carrier in SAFER.",
      keepWhen: "Verified carrier with explicit public dispatch request signal.",
      recordFields: ["Company Name", "Exact Public Request", "Signal Date", "Decision Maker", "Source"]
    },
    {
      id: 38,
      name: "Growth & Fleet-Expansion Signals",
      category: "intent",
      type: "Growth Intent Prioritization",
      url: "https://www.google.com/",
      why: "Prioritize carriers demonstrating active operational growth, driver hiring, and truck acquisitions.",
      searchTerms: ['"trucking company" "hiring drivers"', 'carrier "adding trucks"', '"fleet expansion" trucking', '"trucking company" "new location"'],
      procedure: "1. Search growth trigger phrases. 2. Extract company. 3. Verify fleet size & driver capacity.",
      keepWhen: "Carrier matches ICP and growth signal is verifiable.",
      recordFields: ["Company Name", "Growth Signal", "Date", "Decision Maker", "USDOT"]
    },
    // 39-41: Internal & Strategic Networks
    {
      id: 39,
      name: "Lead Reactivation — Old Database Recovery",
      category: "network",
      type: "Internal Lead Recovery",
      url: "https://www.google.com/",
      why: "Revitalize previous carrier inquiries, uncontacted records, and historical leads before procuring new data.",
      searchTerms: ["Old CRM leads", "Previous carrier inquiries", "Uncontacted trucking prospects"],
      procedure: "1. Ingest historical records. 2. Normalize and check duplicates. 3. Re-verify active status on SAFER.",
      keepWhen: "Old record passes current 10-point qualification standard.",
      recordFields: ["Original Source", "Refreshed Company", "Updated Contact", "Re-verification Date"]
    },
    {
      id: 40,
      name: "Strategic Industry Partnerships",
      category: "network",
      type: "Network-Based Introductions",
      url: "https://www.google.com/",
      why: "Build recurring referral relationships with adjacent service providers (factoring firms, insurance agents, repair shops, fuel card reps).",
      searchTerms: ["trucking factoring companies Texas", "commercial truck insurance brokers Atlanta", "heavy truck repair Dallas", "fleet fuel card reps"],
      procedure: "1. Identify 20 partner organizations. 2. Connect with BD/partnership leads. 3. Process carrier introductions.",
      keepWhen: "Referred carrier is independently verified in SAFER.",
      recordFields: ["Partner Organization", "Partner Contact", "Carrier Lead", "Introduction Date"]
    },
    {
      id: 41,
      name: "Carrier Referral Intake",
      category: "network",
      type: "Internal Referral Processing",
      url: "https://www.google.com/",
      why: "Process direct word-of-mouth recommendations from existing drivers and carrier clients into verified final leads.",
      searchTerms: ["Internal driver referral", "Client carrier recommendation", "Partner referral intake"],
      procedure: "1. Ingest referral details. 2. Perform 10-point verification. 3. Submit approved record to Final Leads.",
      keepWhen: "Referred carrier passes 100% of standard qualification rules.",
      recordFields: ["Referral Source", "Company Name", "Decision Maker", "Verification Date", "Status"]
    },
    // Extended Commercial Directories
    {
      id: 42,
      name: "TruckDown Commercial Fleet Directory",
      category: "commercial",
      type: "Heavy Vehicle Service & Fleet Directory",
      url: "https://www.truckdown.com/",
      why: "Discover commercial transport fleets, heavy towing operations, and regional carrier repair networks.",
      searchTerms: ["Heavy duty transport", "Fleet breakdown directory", "Commercial carrier services"],
      procedure: "1. Search target metro. 2. Filter transportation and carrier operations. 3. Validate via SAFER.",
      keepWhen: "Active carrier entity with verifiable operating equipment.",
      recordFields: ["Company Name", "City/State", "Phone", "Services", "USDOT"]
    },
    {
      id: 43,
      name: "QuickTransportSolutions Carrier Registry",
      category: "commercial",
      type: "Motor Carrier Logistics Directory",
      url: "https://www.quicktransportsolutions.com/",
      why: "Comprehensive public database indexing thousands of small fleets with USDOT numbers, MC numbers, and contact names.",
      searchTerms: ["Carrier search by state", "Trucking companies directory", "USDOT lookup directory"],
      procedure: "1. Search by state/city. 2. Identify candidate fleets. 3. Confirm status on SAFER.",
      keepWhen: "Carrier is ACTIVE and within 2-10 truck fleet ICP.",
      recordFields: ["Company Name", "USDOT", "MC #", "Fleet Count", "City/State"]
    },
    {
      id: 44,
      name: "OOIDA Owner-Operator Directory",
      category: "commercial",
      type: "Independent Carrier Association",
      url: "https://www.ooida.com/",
      why: "Official association representing small-business truckers and independent owner-operators nationwide.",
      searchTerms: ["OOIDA member directory", "Independent truckers network", "Small carrier advocacy"],
      procedure: "1. Consult public directory and publication archives. 2. Verify carrier standing.",
      keepWhen: "Verified independent motor carrier.",
      recordFields: ["Company Name", "Association Reference", "Location", "Source"]
    }
  ];

  // Copy-Paste Search Bank Bank Queries
  const searchBank = {
    carrier_discovery: [
      '"trucking company" "Texas" "owner"',
      '"trucking LLC" "Dallas"',
      '"dry van carrier" Texas',
      '"reefer carrier" Georgia',
      '"small trucking company" Florida',
      '"owner operator" trucking Ohio',
      '"flatbed carrier" "Illinois" "contact"',
      '"hotshot trucking" "Texas" "USDOT"'
    ],
    decision_maker: [
      '"[Company Name]" owner',
      '"[Company Name]" founder',
      '"[Company Name]" president',
      '"[Company Name]" fleet manager',
      '"[Company Name]" operations manager',
      '"[Company Name]" dispatch manager',
      'site:linkedin.com/in/ "[Company Name]" owner',
      'site:linkedin.com/in/ "[Company Name]" "operations"'
    ],
    hiring_intent: [
      '"trucking company" "hiring dispatcher"',
      '"dispatcher needed" trucking',
      '"need a dispatcher" trucking',
      '"looking for dispatch service" carrier',
      '"trucking company" "hiring fleet manager"',
      '"small fleet" "seeking dispatcher"',
      '"carrier" "looking for dedicated dispatcher"'
    ],
    growth_events: [
      '"trucking company" expansion Texas',
      '"carrier" "new terminal"',
      '"carrier" "fleet expansion"',
      '"trucking company" "new trucks"',
      '"transportation company" "adding lanes"',
      'trucking conference exhibitors 2026'
    ],
    case_studies: [
      '"trucking carrier" "case study" TMS',
      '"trucking company" "customer story" software',
      '"carrier success story" factoring',
      '"trucking customer spotlight" insurance',
      '"fleet spotlight" telematics ELD'
    ],
    specialized_verticals: [
      'drayage carriers Los Angeles',
      'reefer carriers Georgia',
      'flatbed carriers Texas',
      'dry van carriers Ohio',
      'container trucking Houston port',
      'trucking companies near Chicago logistics hub'
    ]
  };

  const categories = [
    { id: 'all', label: 'All Methods (44)' },
    { id: 'federal', label: 'Federal & Official (7)' },
    { id: 'commercial', label: 'Commercial Directories (9)' },
    { id: 'b2b', label: 'B2B & Intelligence (3)' },
    { id: 'social', label: 'Social & Community (3)' },
    { id: 'intent', label: 'Hiring & High-Intent (4)' },
    { id: 'tech', label: 'Tech & Case Studies (5)' },
    { id: 'news', label: 'Industry News & Media (3)' },
    { id: 'verticals', label: 'Verticals & Drayage (5)' },
    { id: 'network', label: 'Strategic Networks (3)' }
  ];

  const filteredMethods = searchMethods.filter(method => {
    const matchesCat = activeCategory === 'all' || method.category === activeCategory;
    const matchesSearch = searchTerm === '' || 
      method.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      method.why.toLowerCase().includes(searchTerm.toLowerCase()) ||
      method.type.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesCat && matchesSearch;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      
      {/* Top Banner & Standard Definition */}
      <div className="bento-card" style={{
        background: 'linear-gradient(135deg, #191928 0%, #2A2A40 100%)',
        color: '#FFFFFF',
        padding: '28px 32px'
      }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '20px', flexWrap: 'wrap' }}>
          <div style={{ maxWidth: '780px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
              <span style={{
                fontSize: '0.7rem',
                fontWeight: 800,
                backgroundColor: 'rgba(255, 255, 255, 0.15)',
                color: '#FFFFFF',
                padding: '3px 10px',
                borderRadius: '999px',
                textTransform: 'uppercase',
                letterSpacing: '0.06em'
              }}>
                Master SOP & Playbook
              </span>
              <span style={{ fontSize: '0.75rem', color: '#CBD5E1' }}>
                41+ Discovery & Verification Methods &bull; Updated September 2026
              </span>
            </div>

            <h1 style={{ fontSize: '1.65rem', fontWeight: 800, letterSpacing: '-0.02em', color: '#FFFFFF', margin: '0 0 10px 0', lineHeight: 1.2 }}>
              U.S. Trucking Lead Generation System
            </h1>

            <p style={{ fontSize: '0.875rem', color: '#E2E8F0', lineHeight: 1.5, margin: 0 }}>
              <strong>The Golden Standard:</strong> A lead is not final just because a company exists. It becomes final when the company is relevant, verified on SAFER/L&amp;I, the correct decision-maker is identified, contact data is usable, the source is recorded, and the record is free of duplicates.
            </p>
          </div>

          <div style={{
            backgroundColor: 'rgba(255, 255, 255, 0.08)',
            border: '1px solid rgba(255, 255, 255, 0.15)',
            borderRadius: 'var(--radius-md)',
            padding: '16px 20px',
            minWidth: '240px'
          }}>
            <div style={{ fontSize: '0.7rem', fontWeight: 700, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '6px' }}>
              Target ICP Range
            </div>
            <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#FFFFFF' }}>
              2 &ndash; 10 Power Units
            </div>
            <div style={{ fontSize: '0.75rem', color: '#CBD5E1', marginTop: '4px' }}>
              Small U.S. Carriers &bull; Owner-Operators
            </div>
          </div>
        </div>

        {/* Pipeline Stages Progress Bar */}
        <div style={{ 
          marginTop: '24px', 
          paddingTop: '20px', 
          borderTop: '1px solid rgba(255, 255, 255, 0.12)',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
          gap: '12px'
        }}>
          {[
            { step: '1. Discovery', desc: 'FMCSA, Maps, Jobs, News' },
            { step: '2. Verification', desc: 'SAFER, L&I, Safety records' },
            { step: '3. Enrichment', desc: 'Owner / Fleet contacts' },
            { step: '4. Scoring', desc: 'A/B/C Priority Matrix' },
            { step: '5. Deduplication', desc: 'Multi-key master check' },
            { step: '6. Final Handoff', desc: 'Approved outreach records' }
          ].map((st, i) => (
            <div key={i} style={{ 
              backgroundColor: 'rgba(255, 255, 255, 0.05)', 
              padding: '10px 14px', 
              borderRadius: 'var(--radius-sm)',
              border: '1px solid rgba(255, 255, 255, 0.08)'
            }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#FFFFFF' }}>{st.step}</div>
              <div style={{ fontSize: '0.675rem', color: '#94A3B8', marginTop: '2px' }}>{st.desc}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Navigation Tabs */}
      <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '12px', flexWrap: 'wrap' }}>
        {[
          { id: 'directory', label: 'All 41+ Methods & Websites', icon: BookOpen },
          { id: 'search_bank', label: 'Boolean Search Bank', icon: Search },
          { id: 'routines', label: 'Daily Search Routines', icon: Clock },
          { id: 'scoring', label: 'Scoring Calculator & Rubric', icon: Scale },
          { id: 'qc', label: '10-Point QC & Rejection Rules', icon: ShieldCheck }
        ].map(tab => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 16px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: isActive ? 'var(--text-dark)' : '#FFFFFF',
                color: isActive ? '#FFFFFF' : 'var(--text-secondary)',
                border: '1px solid',
                borderColor: isActive ? 'var(--text-dark)' : 'var(--border-subtle)',
                fontSize: '0.8rem',
                fontWeight: isActive ? 700 : 500,
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
            >
              <Icon size={15} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* TAB 1: ALL 41+ METHODS DIRECTORY */}
      {activeTab === 'directory' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Controls: Search + Categories */}
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              {categories.map(cat => (
                <button
                  key={cat.id}
                  onClick={() => setActiveCategory(cat.id)}
                  style={{
                    padding: '5px 12px',
                    borderRadius: '999px',
                    fontSize: '0.725rem',
                    fontWeight: activeCategory === cat.id ? 700 : 500,
                    backgroundColor: activeCategory === cat.id ? 'var(--terracotta)' : '#FFFFFF',
                    color: activeCategory === cat.id ? '#FFFFFF' : 'var(--text-secondary)',
                    border: '1px solid',
                    borderColor: activeCategory === cat.id ? 'var(--terracotta)' : 'var(--border-subtle)',
                    cursor: 'pointer'
                  }}
                >
                  {cat.label}
                </button>
              ))}
            </div>

            <div style={{ position: 'relative', width: '280px' }}>
              <Search size={14} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input
                type="text"
                placeholder="Search methods, directories, keywords..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                style={{
                  width: '100%',
                  padding: '7px 12px 7px 32px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-subtle)',
                  fontSize: '0.775rem',
                  backgroundColor: '#FFFFFF',
                  color: 'var(--text-dark)'
                }}
              />
            </div>
          </div>

          {/* Directory Grid */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(440px, 1fr))',
            gap: '16px'
          }}>
            {filteredMethods.map((method) => (
              <div key={method.id} className="bento-card" style={{
                padding: '20px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                borderLeft: '4px solid var(--terracotta)'
              }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '10px', marginBottom: '8px' }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{
                          fontSize: '0.65rem',
                          fontWeight: 800,
                          backgroundColor: 'var(--warm-cream)',
                          color: 'var(--terracotta-dark)',
                          padding: '2px 8px',
                          borderRadius: '999px'
                        }}>
                          Method #{method.id}
                        </span>
                        <span style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-muted)' }}>
                          {method.type}
                        </span>
                      </div>
                      <h3 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-dark)', margin: '6px 0 0 0' }}>
                        {method.name}
                      </h3>
                    </div>

                    <a
                      href={method.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="button-ghost"
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        fontSize: '0.725rem',
                        padding: '4px 10px',
                        borderRadius: 'var(--radius-sm)',
                        textDecoration: 'none',
                        color: 'var(--terracotta)',
                        fontWeight: 600
                      }}
                    >
                      <span>Open Link</span>
                      <ExternalLink size={12} />
                    </a>
                  </div>

                  <p style={{ fontSize: '0.775rem', color: 'var(--text-secondary)', lineHeight: 1.45, margin: '8px 0 14px 0' }}>
                    {method.why}
                  </p>

                  <div style={{
                    backgroundColor: 'var(--sand-light)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '10px 12px',
                    marginBottom: '12px',
                    fontSize: '0.725rem'
                  }}>
                    <div style={{ fontWeight: 700, color: 'var(--text-dark)', marginBottom: '4px' }}>
                      Exact Search Bank Terms:
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                      {method.searchTerms.map((term, idx) => (
                        <span key={idx} style={{
                          backgroundColor: '#FFFFFF',
                          border: '1px solid var(--border-subtle)',
                          padding: '2px 6px',
                          borderRadius: '4px',
                          fontFamily: 'monospace',
                          fontSize: '0.675rem',
                          color: 'var(--text-dark)'
                        }}>
                          {term}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div style={{ fontSize: '0.725rem', color: 'var(--text-secondary)', lineHeight: 1.4, marginBottom: '10px' }}>
                    <strong style={{ color: 'var(--text-dark)' }}>Procedure: </strong>
                    {method.procedure}
                  </div>
                </div>

                <div style={{
                  borderTop: '1px solid var(--border-subtle)',
                  paddingTop: '10px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  fontSize: '0.7rem'
                }}>
                  <div style={{ color: 'var(--sage-dark)', fontWeight: 600 }}>
                    &bull; Keep when: {method.keepWhen}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 2: COPY-PASTE SEARCH BANK */}
      {activeTab === 'search_bank' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div className="bento-card" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <Search size={18} color="var(--terracotta)" />
              <h2 style={{ fontSize: '1.1rem', fontWeight: 800, margin: 0, color: 'var(--text-dark)' }}>
                Master Boolean Search Bank
              </h2>
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: 0 }}>
              Decision Rule: Use these copy-paste search strings for initial discovery; never treat the search snippet as final verification.
            </p>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '16px' }}>
            {[
              { title: '1. Carrier Discovery', queries: searchBank.carrier_discovery, icon: Building2, tag: 'Discovery' },
              { title: '2. Decision-Maker Discovery', queries: searchBank.decision_maker, icon: Briefcase, tag: 'Enrichment' },
              { title: '3. High-Intent & Hiring Signals', queries: searchBank.hiring_intent, icon: Flame, tag: 'Intent' },
              { title: '4. Growth & Fleet Expansion Events', queries: searchBank.growth_events, icon: Sparkles, tag: 'Priority' },
              { title: '5. Technology & Case Studies', queries: searchBank.case_studies, icon: Cpu, tag: 'Tech' },
              { title: '6. Specialized Logistics Verticals', queries: searchBank.specialized_verticals, icon: Anchor, tag: 'Verticals' }
            ].map((section, idx) => {
              const SectionIcon = section.icon;
              return (
                <div key={idx} className="bento-card" style={{ padding: '20px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <SectionIcon size={16} color="var(--terracotta)" />
                      <h3 style={{ fontSize: '0.925rem', fontWeight: 700, margin: 0, color: 'var(--text-dark)' }}>
                        {section.title}
                      </h3>
                    </div>
                    <span style={{
                      fontSize: '0.65rem',
                      fontWeight: 700,
                      backgroundColor: 'var(--sand-light)',
                      color: 'var(--text-secondary)',
                      padding: '2px 8px',
                      borderRadius: '999px'
                    }}>
                      {section.tag}
                    </span>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {section.queries.map((q, qIdx) => {
                      const id = `q-${idx}-${qIdx}`;
                      const isCopied = copiedId === id;
                      return (
                        <div key={qIdx} style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          backgroundColor: '#FFFFFF',
                          border: '1px solid var(--border-subtle)',
                          padding: '8px 12px',
                          borderRadius: 'var(--radius-sm)',
                          gap: '10px'
                        }}>
                          <code style={{ fontSize: '0.75rem', color: 'var(--text-dark)', wordBreak: 'break-all' }}>
                            {q}
                          </code>
                          <button
                            onClick={() => handleCopy(q, id)}
                            style={{
                              backgroundColor: isCopied ? 'var(--sage)' : 'var(--sand-light)',
                              color: isCopied ? 'var(--sage-dark)' : 'var(--text-dark)',
                              border: 'none',
                              padding: '4px 8px',
                              borderRadius: '4px',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '4px',
                              fontSize: '0.675rem',
                              fontWeight: 600,
                              flexShrink: 0
                            }}
                          >
                            {isCopied ? <Check size={12} /> : <Copy size={12} />}
                            <span>{isCopied ? 'Copied' : 'Copy'}</span>
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* TAB 3: DAILY SEARCH ROUTINES */}
      {activeTab === 'routines' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div className="bento-card" style={{ padding: '20px' }}>
            <h2 style={{ fontSize: '1.1rem', fontWeight: 800, margin: '0 0 8px 0', color: 'var(--text-dark)' }}>
              Repeatable Daily Lead Generation Routines
            </h2>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: 0 }}>
              Because your job is final leads only, the objective is to operate a repeatable production line for clean, verified, ready-to-contact records.
            </p>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '16px' }}>
            {[
              {
                routine: 'Routine A — Direct Discovery',
                flow: 'FMCSA SAFER -> Google Maps/Search -> Company Website -> LinkedIn / Apollo -> Final Verification',
                target: 'Core volume carrier generation',
                desc: 'Best for building solid baseline batches of active carriers in targeted regional state clusters.'
              },
              {
                routine: 'Routine B — Intent Discovery',
                flow: 'Indeed / LinkedIn Jobs -> Identify Employer Carrier -> Verify SAFER -> Decision Maker -> Final Lead',
                target: 'High-conversion dispatch leads',
                desc: 'Targets carriers experiencing operational surge, driver shortage, or dispatch bottlenecks.'
              },
              {
                routine: 'Routine C — News / Expansion Events',
                flow: 'FreightWaves / TTNews / Google News -> Named Carrier -> Verify Fleet Size -> Enrich -> Final Lead',
                target: 'Growing fleets adding capacity',
                desc: 'Identifies fleets that just purchased trucks or opened new terminal yards.'
              },
              {
                routine: 'Routine D — Technology Ecosystems',
                flow: 'G2 / Software Advice / Factoring Case Studies -> Named Carrier -> SAFER Verify -> Decision Maker',
                target: 'Tech-enabled modern carriers',
                desc: 'Extracts small fleets with active TMS, ELD, and factoring relationships.'
              },
              {
                routine: 'Routine E — Strategic Networks & Associations',
                flow: 'State ATA Association / Partner / Referral -> Carrier Entity -> Verify -> Enrich -> Final Lead',
                target: 'Established reputable carriers',
                desc: 'Draws from state trucking associations (TXTA, FTA, GMTA) and strategic partners.'
              }
            ].map((r, i) => (
              <div key={i} className="bento-card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                    <h3 style={{ fontSize: '0.95rem', fontWeight: 700, margin: 0, color: 'var(--text-dark)' }}>
                      {r.routine}
                    </h3>
                  </div>
                  <div style={{
                    backgroundColor: 'var(--warm-cream)',
                    padding: '8px 12px',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    color: 'var(--terracotta-dark)',
                    margin: '10px 0',
                    lineHeight: 1.4
                  }}>
                    {r.flow}
                  </div>
                  <p style={{ fontSize: '0.775rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                    {r.desc}
                  </p>
                </div>
                <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-muted)', borderTop: '1px solid var(--border-subtle)', paddingTop: '10px' }}>
                  Target: {r.target}
                </div>
              </div>
            ))}
          </div>

          {/* Daily Work Schedule Allocation */}
          <div className="bento-card" style={{ padding: '24px' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 700, margin: '0 0 16px 0', color: 'var(--text-dark)' }}>
              Standard Daily Production Time Blocks
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
              {[
                { time: '30 min', action: 'Confirm ICP & Target States', output: 'Approved Criteria' },
                { time: '90 min', action: 'Multi-Source Discovery (FMCSA + Maps)', output: '20-30 Raw Prospects' },
                { time: '60 min', action: 'Verify Active Carrier & Authority Fit', output: '10-15 Qualified Records' },
                { time: '60 min', action: 'Enrich Decision-Makers & Direct Dials', output: '8-12 Enriched Records' },
                { time: '30 min', action: 'Deduplicate, Score & 10-Point QC', output: 'Final Lead Batch' },
                { time: '15 min', action: 'Handoff to Sheets / CRM', output: 'Clean Final Submission' }
              ].map((b, i) => (
                <div key={i} style={{
                  padding: '14px',
                  backgroundColor: '#FFFFFF',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-subtle)'
                }}>
                  <div style={{ fontSize: '0.75rem', fontWeight: 800, color: 'var(--terracotta)' }}>{b.time}</div>
                  <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-dark)', margin: '4px 0' }}>{b.action}</div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Output: {b.output}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: SCORING CALCULATOR & RUBRIC */}
      {activeTab === 'scoring' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
          {/* Interactive Calculator */}
          <div className="bento-card" style={{ padding: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
              <Scale size={20} color="var(--terracotta)" />
              <h2 style={{ fontSize: '1.1rem', fontWeight: 800, margin: 0, color: 'var(--text-dark)' }}>
                Interactive Lead Scoring Calculator
              </h2>
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '20px' }}>
              Toggle the qualification signals to simulate the automated scoring engine.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {[
                { key: 'fleet_range', label: 'Fits Target Fleet Range (2-10 Power Units)', points: '+2 pts' },
                { key: 'active_carrier', label: 'Active / Relevant Carrier Verified (FMCSA SAFER & L&I)', points: '+2 pts' },
                { key: 'decision_maker', label: 'Decision-Maker Identified (Owner/Fleet/Ops Principal)', points: '+2 pts' },
                { key: 'equipment_match', label: 'Relevant Equipment / Service Type Verified', points: '+1 pt' },
                { key: 'usable_contact', label: 'Usable Business Email & Phone Contact', points: '+1 pt' },
                { key: 'intent_signal', label: 'Recent Hiring / Dispatch Intent Signal', points: '+1 pt' },
                { key: 'tech_signal', label: 'Verified Technology / Business-Event Signal', points: '+1 pt' }
              ].map((factor) => (
                <label key={factor.key} style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '10px 14px',
                  backgroundColor: scoreFactors[factor.key] ? 'var(--warm-cream)' : '#FFFFFF',
                  border: '1px solid',
                  borderColor: scoreFactors[factor.key] ? 'var(--terracotta)' : 'var(--border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  cursor: 'pointer'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <input
                      type="checkbox"
                      checked={scoreFactors[factor.key]}
                      onChange={(e) => setScoreFactors({ ...scoreFactors, [factor.key]: e.target.checked })}
                      style={{ cursor: 'pointer' }}
                    />
                    <span style={{ fontSize: '0.775rem', fontWeight: 600, color: 'var(--text-dark)' }}>
                      {factor.label}
                    </span>
                  </div>
                  <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--terracotta)' }}>
                    {factor.points}
                  </span>
                </label>
              ))}
            </div>

            {/* Score Output Banner */}
            <div style={{
              marginTop: '24px',
              padding: '18px',
              backgroundColor: currentTier === 'A' ? 'var(--sage)' : (currentTier === 'B' ? 'var(--warm-cream)' : '#F5C2C0'),
              borderRadius: 'var(--radius-md)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}>
              <div>
                <div style={{ fontSize: '0.7rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Simulated Score Output
                </div>
                <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-dark)' }}>
                  {currentScore} / 10 Points
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <span style={{
                  fontSize: '1.1rem',
                  fontWeight: 800,
                  backgroundColor: '#FFFFFF',
                  color: 'var(--text-dark)',
                  padding: '4px 14px',
                  borderRadius: '999px',
                  boxShadow: 'var(--shadow-subtle)'
                }}>
                  Tier {currentTier} Lead
                </span>
                <div style={{ fontSize: '0.675rem', fontWeight: 600, marginTop: '4px' }}>
                  {currentTier === 'A' ? 'Approved for Immediate Final Handoff' : (currentTier === 'B' ? 'Qualified for Standard Outreach' : 'Review / Needs Additional Enrichment')}
                </div>
              </div>
            </div>
          </div>

          {/* Master Scoring Matrix Reference */}
          <div className="bento-card" style={{ padding: '24px' }}>
            <h2 style={{ fontSize: '1.1rem', fontWeight: 800, margin: '0 0 16px 0', color: 'var(--text-dark)' }}>
              Master SOP Scoring Rubric
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div style={{ padding: '14px', backgroundColor: '#FFFFFF', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <strong style={{ fontSize: '0.85rem', color: 'var(--sage-dark)' }}>Tier A (8 &ndash; 10 Points)</strong>
                  <span style={{ fontSize: '0.7rem', fontWeight: 700, backgroundColor: 'var(--sage)', color: 'var(--sage-dark)', padding: '2px 8px', borderRadius: '999px' }}>High Priority</span>
                </div>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', margin: '6px 0 0 0' }}>
                  Meets full ICP fleet range, 100% verified active operating authority on SAFER/L&amp;I, direct owner/ops contact identified with verified email/phone, plus an active hiring or tech intent signal.
                </p>
              </div>

              <div style={{ padding: '14px', backgroundColor: '#FFFFFF', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <strong style={{ fontSize: '0.85rem', color: 'var(--terracotta-dark)' }}>Tier B (6.0 &ndash; 7.9 Points)</strong>
                  <span style={{ fontSize: '0.7rem', fontWeight: 700, backgroundColor: 'var(--warm-cream)', color: 'var(--terracotta-dark)', padding: '2px 8px', borderRadius: '999px' }}>Standard Qualified</span>
                </div>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', margin: '6px 0 0 0' }}>
                  Verified carrier with active authority, correct fleet range, and usable business contact. Ready for cold email and outbound calling.
                </p>
              </div>

              <div style={{ padding: '14px', backgroundColor: '#FFFFFF', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <strong style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Tier C (5.0 &ndash; 5.9 Points)</strong>
                  <span style={{ fontSize: '0.7rem', fontWeight: 700, backgroundColor: 'var(--sand-light)', color: 'var(--text-secondary)', padding: '2px 8px', borderRadius: '999px' }}>Minimum ICP Fit</span>
                </div>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', margin: '6px 0 0 0' }}>
                  Meets base ICP criteria and holds active authority, but requires additional enrichment (decision maker identification or verified email/phone) before outreach.
                </p>
              </div>

              <div style={{ padding: '14px', backgroundColor: '#FFFFFF', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <strong style={{ fontSize: '0.85rem', color: '#991B1B' }}>Below ICP Threshold (&lt; 5.0 Points)</strong>
                  <span style={{ fontSize: '0.7rem', fontWeight: 700, backgroundColor: '#FEE2E2', color: '#991B1B', padding: '2px 8px', borderRadius: '999px' }}>Needs Enrichment</span>
                </div>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', margin: '6px 0 0 0' }}>
                  Score is below minimum qualification threshold of 5.0; queued in NEEDS_ENRICHMENT for automated multi-tier contact and authority enrichment.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 5: 10-POINT QC & REJECTION RULES */}
      {activeTab === 'qc' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
          {/* 10-Point Grounded Checklist */}
          <div className="bento-card" style={{ padding: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
              <CheckCircle2 size={20} color="var(--sage-dark)" />
              <h2 style={{ fontSize: '1.1rem', fontWeight: 800, margin: 0, color: 'var(--text-dark)' }}>
                10-Point Quality Control Checklist
              </h2>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {[
                "1. Company name and website match.",
                "2. Company is a target trucking/carrier business (not a broker/intermediary).",
                "3. Activity/status is checked on FMCSA SAFER & L&I.",
                "4. Fleet size is supported by data or explicitly marked unknown.",
                "5. Equipment (Dry Van, Reefer, Flatbed) is supported if recorded.",
                "6. Decision-maker name and title are confirmed.",
                "7. Business contact belongs to the company/contact.",
                "8. Source URL and discovery name are recorded.",
                "9. Reason for qualification is recorded.",
                "10. Multi-key deduplication completed by name, domain, phone & USDOT."
              ].map((rule, i) => (
                <div key={i} style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  padding: '8px 12px',
                  backgroundColor: '#FFFFFF',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-subtle)',
                  fontSize: '0.775rem',
                  color: 'var(--text-dark)',
                  fontWeight: 500
                }}>
                  <Check size={14} color="var(--sage-dark)" />
                  <span>{rule}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Rejection Criteria & Compliance */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div className="bento-card" style={{ padding: '24px', borderLeft: '4px solid #DC2626' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
                <XCircle size={20} color="#DC2626" />
                <h2 style={{ fontSize: '1.1rem', fontWeight: 800, margin: 0, color: 'var(--text-dark)' }}>
                  Mandatory Rejection Conditions
                </h2>
              </div>
              <ul style={{ fontSize: '0.775rem', color: 'var(--text-secondary)', lineHeight: 1.6, paddingLeft: '18px', margin: 0 }}>
                <li><strong>Inactive Authority:</strong> Out of service or revoked operating authority on SAFER.</li>
                <li><strong>Logistics Broker Only:</strong> Pure freight broker without motor carrier power units when target is carriers.</li>
                <li><strong>No Identifiable Identity:</strong> Anonymous forum poster or unverifiable shell entity.</li>
                <li><strong>Guessed Data:</strong> Any record containing estimated or fabricated critical fields.</li>
                <li><strong>Unusable Contact:</strong> No valid business phone or verified email domain.</li>
                <li><strong>Duplicate Record:</strong> Matches an existing USDOT, phone, or company domain.</li>
              </ul>
            </div>

            {/* Data-Use & CAN-SPAM Compliance Boundary */}
            <div className="bento-card" style={{ padding: '20px', backgroundColor: 'var(--sand-light)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                <ShieldCheck size={16} color="var(--terracotta)" />
                <h3 style={{ fontSize: '0.875rem', fontWeight: 700, margin: 0, color: 'var(--text-dark)' }}>
                  CAN-SPAM &amp; Outreach Compliance Standard
                </h3>
              </div>
              <p style={{ fontSize: '0.725rem', color: 'var(--text-secondary)', lineHeight: 1.45, margin: 0 }}>
                All collected records must adhere to commercial email requirements: accurate sender identity, non-deceptive subject lines, physical postal address inclusion, and clean opt-out processing. The FTC enforces CAN-SPAM across all B2B commercial outreach.
              </p>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

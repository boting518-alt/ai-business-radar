export const locales = ["zh-CN", "en-US"] as const;
export type Locale = (typeof locales)[number];

export const messages = {
  "zh-CN": {
    "evidence.title":"关联证据",
    "evidence.summary":"证据覆盖",
    "evidence.related":"查看全部关联信号",
    "evidence.empty":"暂无关联证据",
    "evidence.filteredEmpty":"当前筛选或页码下没有证据",
    "evidence.incomplete":"存在关联信号，但部分来源暂不可显示",
    "evidence.countHint":"关联信号按记录计数；视频和频道去重计数，不代表独立验证。",
    "evidence.total":"当前筛选证据总数",
    "evidence.linked":"关联信号",
    "evidence.supporting":"支持信号",
    "evidence.videos":"来源视频（去重）",
    "evidence.channels":"来源频道（去重）",
    "evidence.canonical":"英文规范文本（提取结果）",
    "evidence.canonicalHint":"规范文本是提取结果，未必是来源的逐字引用。",
    "evidence.rawComment":"来源评论原文",
    "evidence.parentVideo":"评论来源于该视频",
    "evidence.unavailable":"来源链接暂不可用，已保留证据文本",
    "evidence.openSource":"打开来源",
    "evidence.sourceHint":"来源链接基于已保存记录，未检查远端可用性。",
    "evidence.explicit":"显式证据",
    "evidence.unknownClaim":"未标注声明类型",
    "evidence.context":"当前机会",
    "evidence.stale":"译文已过期，显示英文规范文本",

    "nav.radar":"雷达","nav.opportunities":"机会","nav.signals":"信号","nav.watchlist":"关注","nav.review":"人工审核","nav.discovery":"数据发现",
    "shell.subtitle":"YouTube 商业情报终端","shell.workspace":"情报工作台","shell.reviewWorkspace":"审核工作区","shell.operations":"运营管理","shell.admin":"管理员","shell.signedIn":"已登录用户","shell.language":"情报语言",
    "signals.title":"商业信号","signals.description":"按观察时间展示已激活、可追溯证据的商业信号。","signals.type":"信号类型","signals.allTypes":"全部类型","signals.industry":"行业","signals.customer":"客户","signals.observedAfter":"观察时间晚于","signals.opportunityId":"机会 ID","signals.apply":"应用筛选","signals.clear":"清除筛选","signals.evidence":"证据摘录","signals.translatedEvidence":"译文证据","signals.original":"查看原文","signals.hideOriginal":"收起原文","signals.claim":"声明类型","signals.source":"来源","signals.video":"视频","signals.channel":"频道","signals.sourceType":"来源类型","signals.linkedOpportunity":"关联机会","signals.noOpportunity":"尚未关联已发布机会","signals.confidence":"置信度","signals.evidenceStrength":"证据强度","signals.previous":"上一页","signals.next":"下一页","signals.offset":"偏移量","signals.pagination":"信号分页","signals.loading":"正在加载商业信号","signals.empty":"目前还没有已激活的商业信号","signals.filteredEmpty":"没有符合筛选条件的信号","signals.emptyDescription":"信号通过审核后会按观察时间显示。","signals.filteredDescription":"调整或清除筛选后重试。","signals.forbidden":"你没有查看信号的权限","signals.loadError":"无法加载商业信号","signals.confidenceHint":"模型提取置信度，并非事实真实性概率","signals.originalEvidence":"英文规范证据（提取结果）",
  },
  "en-US": {
    "evidence.title":"Related evidence",
    "evidence.summary":"Evidence coverage",
    "evidence.related":"View all related Signals",
    "evidence.empty":"No related evidence yet",
    "evidence.filteredEmpty":"No evidence for this filter or page",
    "evidence.incomplete":"Linked signals exist, but some sources cannot be displayed",
    "evidence.countHint":"Signals count records; videos and channels are distinct sources, not independent verification.",
    "evidence.total":"Evidence matching this filter",
    "evidence.linked":"Linked signals",
    "evidence.supporting":"Supporting signals",
    "evidence.videos":"Distinct source videos",
    "evidence.channels":"Distinct source channels",
    "evidence.canonical":"Canonical English text (extracted)",
    "evidence.canonicalHint":"Canonical text is extracted intelligence, not necessarily a verbatim source quotation.",
    "evidence.rawComment":"Original source comment",
    "evidence.parentVideo":"Comment from this video",
    "evidence.unavailable":"Source link unavailable; evidence text retained",
    "evidence.openSource":"Open source",
    "evidence.sourceHint":"Link uses stored provenance; remote availability has not been checked.",
    "evidence.explicit":"Explicit evidence",
    "evidence.unknownClaim":"Claim type not specified",
    "evidence.context":"Current opportunity",
    "evidence.stale":"Translation is stale; showing canonical English text",

    "nav.radar":"Radar","nav.opportunities":"Opportunities","nav.signals":"Signals","nav.watchlist":"Watchlist","nav.review":"Review","nav.discovery":"Discovery",
    "shell.subtitle":"YouTube intelligence terminal","shell.workspace":"Intelligence Workspace","shell.reviewWorkspace":"Review workspace","shell.operations":"Operations","shell.admin":"Admin","shell.signedIn":"Signed-in user","shell.language":"Intelligence language",
    "signals.title":"Commercial Signals","signals.description":"Active, traceable commercial signals ordered by observation time.","signals.type":"Signal Type","signals.allTypes":"All types","signals.industry":"Industry","signals.customer":"Customer","signals.observedAfter":"Observed After","signals.opportunityId":"Opportunity ID","signals.apply":"Apply Filters","signals.clear":"Clear Filters","signals.evidence":"Evidence","signals.translatedEvidence":"Translated Evidence","signals.original":"Show original","signals.hideOriginal":"Hide original","signals.claim":"Claim Type","signals.source":"Source","signals.video":"Video","signals.channel":"Channel","signals.sourceType":"Source Type","signals.linkedOpportunity":"Linked Opportunity","signals.noOpportunity":"No published opportunity linked","signals.confidence":"Confidence","signals.evidenceStrength":"Evidence Strength","signals.previous":"Previous","signals.next":"Next","signals.offset":"Offset","signals.pagination":"Signal pagination","signals.loading":"Loading commercial signals","signals.empty":"No active commercial signals yet","signals.filteredEmpty":"No signals match these filters","signals.emptyDescription":"Signals appear here after review and activation.","signals.filteredDescription":"Adjust or clear the filters and try again.","signals.forbidden":"You do not have permission to view signals","signals.loadError":"Unable to load commercial signals","signals.confidenceHint":"Model extraction confidence, not probability that the claim is factual","signals.originalEvidence":"Canonical English evidence (extracted)",
  },
} as const;

export type TranslationKey = keyof (typeof messages)["en-US"];

const enumLabels: Record<Locale, Record<string,string>> = {
  "zh-CN": {supporting:"支持",contradicting:"反对",context:"背景",candidate_match:"候选匹配",workflow:"工作流",technology:"技术",pain:"痛点",demand:"需求",pricing:"定价",purchase_intent:"购买意向",feature_request:"功能请求",complaint:"投诉",competition:"竞争",revenue:"营收",customer:"客户",product_launch:"产品发布",growth:"增长",distribution:"分销",market_change:"市场变化",adoption:"采用",fact:"事实",creator_claim:"创作者声明",inferred:"推断",opinion:"观点",speculation:"推测",unknown:"未知",candidate:"候选",active:"已发布",publish:"发布",defer:"暂缓",invalid:"无效",video:"YouTube 视频",comment:"YouTube 评论",youtube_video:"YouTube 视频",youtube_comment:"YouTube 评论",manual:"人工证据",market_context:"市场背景"},
  "en-US": {supporting:"Supporting",contradicting:"Contradicting",context:"Context",candidate_match:"Candidate match",workflow:"Workflow",technology:"Technology",pain:"Pain",demand:"Demand",pricing:"Pricing",purchase_intent:"Purchase intent",feature_request:"Feature request",complaint:"Complaint",competition:"Competition",revenue:"Revenue",customer:"Customer",product_launch:"Product launch",growth:"Growth",distribution:"Distribution",market_change:"Market change",adoption:"Adoption",fact:"Fact",creator_claim:"Creator claim",inferred:"Inferred",opinion:"Opinion",speculation:"Speculation",unknown:"Unknown",candidate:"Candidate",active:"Active",publish:"Publish",defer:"Defer",invalid:"Invalid",video:"YouTube Video",comment:"YouTube Comment",youtube_video:"YouTube Video",youtube_comment:"YouTube Comment",manual:"Manual evidence",market_context:"Market context"},
};

export function enumLabel(locale:Locale,value:string){return enumLabels[locale][value]??value}

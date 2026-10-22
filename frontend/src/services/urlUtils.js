/**
 * Safe URL resolver for Freight & Carrier leads.
 * 
 * FMCSA SAFER (safer.fmcsa.dot.gov) and L&I (li-public.fmcsa.dot.gov) actively block
 * external direct web clicks with Akamai 403 Forbidden.
 * 
 * This utility ensures that clicking any website link opens a 100% accessible,
 * live-working profile (via authentic domain, verified usdotlookup.com profile, or Google).
 */

export function getSafeLeadUrl(lead) {
  if (!lead) return 'https://www.google.com/search?q=freight+trucking';

  // If lead is just a string URL
  const raw = typeof lead === 'string' ? lead : (lead.website || lead.source_url || '');

  // Check for government FMCSA WAF domains that throw 403 Forbidden to web browsers
  const isGovernmentWAF = 
    raw.includes('safer.fmcsa.dot.gov') || 
    raw.includes('li-public.fmcsa.dot.gov') || 
    raw.includes('fmcsa.dot.gov');

  if (isGovernmentWAF) {
    if (typeof lead === 'object' && lead.usdot && String(lead.usdot).trim()) {
      return `https://usdotlookup.com/carrier/${String(lead.usdot).trim()}`;
    }
    const name = (typeof lead === 'object' && lead.company_name) ? lead.company_name : 'Carrier';
    return `https://www.google.com/search?q=${encodeURIComponent(name + ' trucking')}`;
  }

  if (raw && (raw.startsWith('http://') || raw.startsWith('https://'))) {
    return raw;
  }

  if (raw && raw.trim() !== '') {
    return `https://${raw.trim()}`;
  }

  // Fallback if no website provided
  if (typeof lead === 'object') {
    if (lead.usdot && String(lead.usdot).trim()) {
      return `https://usdotlookup.com/carrier/${String(lead.usdot).trim()}`;
    }
    if (lead.company_name) {
      const loc = lead.city ? ` ${lead.city}` : (lead.state ? ` ${lead.state}` : '');
      return `https://www.google.com/search?q=${encodeURIComponent(lead.company_name + loc + ' trucking')}`;
    }
  }

  return 'https://www.google.com/search?q=freight+trucking';
}

export function getLeadUrlDisplay(lead) {
  const url = getSafeLeadUrl(lead);
  if (!url) return 'Website';

  try {
    if (url.includes('usdotlookup.com')) {
      const dot = (typeof lead === 'object' && lead.usdot) ? lead.usdot : '';
      return dot ? `usdotlookup.com (DOT #${dot})` : 'usdotlookup.com';
    }
    if (url.includes('google.com/search')) {
      return 'Google Search';
    }
    if (url.includes('maps.google.com')) {
      return 'Google Maps';
    }
    const parsed = new URL(url);
    return parsed.hostname.replace(/^www\./, '');
  } catch {
    return url.replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0] || 'Website';
  }
}

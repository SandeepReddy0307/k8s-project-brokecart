import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { CART_KEY, money, readCart, updateQuantity, type Cart } from './cart';
import './styles.css';
import {useCommerce, commerceApi} from './commerce';

type Product = { id: string; name: string; category: string; description: string; priceCents: number; currency: string; artwork: string; badge: string };
type Quote = { quoteId: string; subtotalCents: number; discountCents: number; shippingCents: number; totalCents: number; expiresAt: string;
  lines: { productId: string; name: string; quantity: number; unitPriceCents: number; totalCents: number }[] };
async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, { ...options, signal: options.signal || AbortSignal.timeout(12000) });
  if (!response.ok) {
    const problem = await response.json().catch(() => null);
    throw new Error(problem?.detail || `Request failed (${response.status}). Please try again.`);
  }
  return response.json() as Promise<T>;
}
function Icon({ name }: { name: 'cart' | 'search' | 'arrow' | 'close' }) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {name === 'cart' ? <><path d="M3 4h3l3 12h10l3-9H7"/><circle cx="10" cy="20" r="1"/><circle cx="18" cy="20" r="1"/></> :
      name === 'search' ? <><circle cx="10" cy="10" r="6"/><path d="m15 15 5 5"/></> :
      name === 'close' ? <path d="m6 6 12 12M18 6 6 18"/> : <path d="M4 12h16m-6-6 6 6-6 6"/>}
  </svg>;
}
function App() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reload, setReload] = useState(0);
  const [category, setCategory] = useState('All finds');
  const [search, setSearch] = useState('');
  const [cart, setCart] = useState<Cart>(() => { try { return readCart(localStorage.getItem(CART_KEY)); } catch { return {}; } });
  const [open, setOpen] = useState(false);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [quoteError, setQuoteError] = useState('');
  const [promo, setPromo] = useState('');
  const [appliedPromo, setAppliedPromo] = useState('');
  const [announcement, setAnnouncement] = useState('');
  const [searchResults,setSearchResults]=useState<Product[]|null>(null);
  const [searchError,setSearchError]=useState('');
  useEffect(()=>{setSearchError('');setSearchResults(null);if(!search.trim())return;const controller=new AbortController();const timer=setTimeout(()=>commerceApi<{items:Product[]}>(`/api/search/products?q=${encodeURIComponent(search.trim())}`,{signal:AbortSignal.any([controller.signal,AbortSignal.timeout(12000)])}).then(result=>setSearchResults(result.items)).catch(e=>{if(!controller.signal.aborted)setSearchError(e.message);}),250);return()=>{clearTimeout(timer);controller.abort();};},[search]);
  const [sort, setSort] = useState('featured');
  const [details, setDetails] = useState<Product | null>(null);
  const cartDialog = useRef<HTMLDialogElement>(null);
  const detailsDialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    api<{ items: Product[] }>('/api/catalog/products?size=100', { signal: AbortSignal.any([controller.signal, AbortSignal.timeout(12000)]) })
      .then(data => setProducts(data.items)).catch(e => { if (!controller.signal.aborted) setError(e.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [reload]);
  useEffect(() => { try { localStorage.setItem(CART_KEY, JSON.stringify(cart)); } catch { /* Cart still works in this tab. */ } }, [cart]);
  const commerce=useCommerce(cart,setCart,products,()=>setOpen(false));
  const count = Object.values(cart).reduce((sum, quantity) => sum + quantity, 0);
  useEffect(() => {
    setQuote(null); setQuoteError('');
    if (!open || !count) return;
    const controller = new AbortController();
    api<Quote>('/api/pricing/quotes', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items: Object.entries(cart).map(([productId, quantity]) => ({ productId, quantity })), promoCode: appliedPromo }),
      signal: AbortSignal.any([controller.signal, AbortSignal.timeout(12000)])
    }).then(setQuote).catch(e => { if (!controller.signal.aborted) setQuoteError(e.message); });
    return () => controller.abort();
  }, [cart, open, appliedPromo, count]);
  useEffect(() => { if (open) cartDialog.current?.showModal(); else cartDialog.current?.close(); }, [open]);
  useEffect(() => { if (details) detailsDialog.current?.showModal(); else detailsDialog.current?.close(); }, [details]);
  const visible = useMemo(() => {
    const list = (search.trim()?searchResults||[]:products).filter(p => category === 'All finds' || p.category === category);
    return sort === 'featured' ? list : list.sort((a, b) => sort === 'low' ? a.priceCents - b.priceCents : b.priceCents - a.priceCents);
  }, [products, category, search, searchResults, sort]);
  function add(product: Product) {
    commerce.setQuantity(product.id,(cart[product.id]||0)+1);
    setAnnouncement(`${product.name} added to your cart.`);
  }
  return <>
    <div className="announcement">YOUR TASTE IS EXPENSIVE. OUR FINDS AREN’T. <span>Free shipping on orders $100+</span></div>
    <header className="header"><a className="brand" href="#" aria-label="BrokeCart home"><span className="brand-mark"><Icon name="cart"/></span>BrokeCart<span className="brand-dot">.</span></a>
      <nav aria-label="Main navigation"><a href="#finds">Shop the finds</a><a href="#story">Our very good excuse</a></nav>
      <button className="account-button" onClick={()=>commerce.openPanel('account')}>{commerce.user ? 'My account' : 'Sign in'}</button><button className="cart-button" onClick={() => setOpen(true)}><Icon name="cart"/> Your cart <span>{count}</span></button>
    </header>
    <main>
      <section className="hero"><div className="hero-copy"><div className="eyebrow"><span/> LITTLE JOYS. BIG CART ENERGY.</div>
        <h1>Good finds.<br/><span>Questionable</span><br/>restraint.</h1>
        <p>Things you’ll love. Prices you can live with.<br/>Welcome to your next “okay, just one more.”</p>
        <a className="primary" href="#finds">Meet your next favorite <Icon name="arrow"/></a>
        <div className="hero-note"><span>✦</span> Full cart, empty wallet. Worth it, probably.</div>
      </div><div className="hero-art"><div className="hero-orbit"/><div className="hero-art-label">THE DAILY<br/>GOOD STUFF</div>
        <img src="/products/headphones.svg" alt="Cream and charcoal wireless headphones"/>
        <div className="price-sticker">GOOD VIBES<br/><strong>$89.90</strong><span>Cloud Nine Headphones</span></div>
        <div className="floating-tag">YOUR NEW PERSONALITY ↗</div><div className="hero-dots">01 <span>—</span> 08</div>
      </div></section>
      <div className="benefits"><span>↗ Thoughtfully picked</span><span>◇ No boring finds</span><span>♡ A little joy, delivered</span><span>✦ Seriously good prices</span></div>
      <section className="finds" id="finds"><div className="section-top"><div><p className="eyebrow">THE GOOD STUFF, ALL IN ONE PLACE</p><h2>Your next little obsession.</h2></div>
        <label className="search"><Icon name="search"/><input aria-label="Search products" placeholder="Find your kind of thing…" value={search} onChange={e => setSearch(e.target.value)}/></label></div>
        <div className="filter-row"><div className="categories">{['All finds', 'Tech', 'Style', 'Home', 'Outdoors'].map(value => <button key={value} aria-pressed={category === value} className={category === value ? 'selected' : ''} onClick={() => setCategory(value)}>{value}</button>)}</div>
          <label className="sort">Sort by <select aria-label="Sort products" value={sort} onChange={e => setSort(e.target.value)}><option value="featured">Our favorites</option><option value="low">Price: low to high</option><option value="high">Price: high to low</option></select></label></div>
        {loading ? <div className="product-grid" aria-label="Loading products">{Array.from({length: 8}, (_, i) => <div key={i} className="skeleton"/>)}</div> : (error||searchError) ? <div className="empty" role="alert"><h3>Our finds took a detour.</h3><p>{error||searchError}</p><button className="primary" onClick={() => setReload(n => n + 1)}>Try again</button></div> : !visible.length ? <div className="empty"><h3>No finds this time.</h3><p>Try a different search or category.</p></div> :
          <div className="product-grid">{visible.map(p => <article className={`product ${p.artwork}`} key={p.id}><button className="product-image" onClick={() => setDetails(p)} aria-label={`View ${p.name}`}><span className="badge">{p.badge}</span><img src={`/products/${p.artwork}.svg`} alt={p.name} loading="lazy"/></button><div className="product-info"><span className="product-category">{p.category}</span><h3><button onClick={() => setDetails(p)}>{p.name}</button></h3><div className="product-bottom"><strong>{money(p.priceCents)}</strong><button className="add" disabled={(cart[p.id] || 0) >= 10} onClick={() => add(p)} aria-label={`Add ${p.name} to cart`}>+</button></div></div></article>)}</div>}
      </section>
      <section className="story" id="story"><span className="story-star">✳</span><div><p className="eyebrow">WE’RE NOT SAYING YOU NEED IT.</p><h2>But imagine how happy<br/>your cart would be.</h2><p>Everyday essentials with a little extra personality.<br/>Picked for your life. And your slightly impulsive side.</p></div><a className="primary" href="#finds">A little look won’t hurt <Icon name="arrow"/></a></section>
    </main>
    <footer><a className="brand" href="#">BrokeCart.</a><span>Full cart, empty wallet.</span><small>© {new Date().getFullYear()} BrokeCart · A local commerce learning project</small></footer>
    <p className="sr-only" role="status" aria-live="polite">{announcement}</p>
    <dialog ref={cartDialog} className="cart-dialog" onCancel={() => setOpen(false)} onClose={() => setOpen(false)} aria-labelledby="cart-title"><div className="dialog-head"><div><p className="eyebrow">EXCELLENT TASTE, BY THE WAY.</p><h2 id="cart-title">Your cart <span>({count})</span></h2></div><button className="icon-button" aria-label="Close cart" onClick={() => setOpen(false)}><Icon name="close"/></button></div>
      {!count ? <div className="empty"><Icon name="cart"/><h3>A little empty in here.</h3><p>Your next favorite is waiting.</p><button className="primary" onClick={() => setOpen(false)}>Keep exploring</button></div> : <>
        <div className="cart-items">{Object.entries(cart).map(([id, quantity]) => { const p = products.find(product => product.id === id); return <div className="cart-item" key={id}>{p && <img src={`/products/${p.artwork}.svg`} alt=""/>}<div><h3>{p?.name || id}</h3><span>{p ? money(p.priceCents) : 'Price checked by server'}</span><div className="quantity"><button aria-label={`Decrease ${p?.name || id}`} onClick={() => commerce.setQuantity(id,quantity-1)}>−</button><span>{quantity}</span><button disabled={quantity >= 10} aria-label={`Increase ${p?.name || id}`} onClick={() => commerce.setQuantity(id,quantity+1)}>+</button></div></div><button className="remove" onClick={() => commerce.setQuantity(id,0)}>Remove</button></div>; })}</div>
        <form className="promo" onSubmit={e => {e.preventDefault(); setAppliedPromo(promo.trim().toUpperCase());}}><input aria-label="Promotion code" placeholder="Promo code? Try BROKE10" maxLength={30} value={promo} onChange={e => setPromo(e.target.value)}/><button type="submit">Apply</button></form>
        <div className="quote" aria-live="polite">{quoteError ? <p className="error" role="alert">{quoteError}</p> : !quote ? <p>Checking your prices…</p> : <><div><span>Subtotal</span><span>{money(quote.subtotalCents)}</span></div>{quote.discountCents > 0 && <div className="discount"><span>BROKE10 · 10% off</span><span>−{money(quote.discountCents)}</span></div>}<div><span>Shipping</span><span>{quote.shippingCents ? money(quote.shippingCents) : 'On us'}</span></div><div className="total"><strong>Total</strong><strong>{money(quote.totalCents)}</strong></div><small>Quote valid until {new Date(quote.expiresAt).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}. Taxes are not included in this first application milestone.</small></>}</div>
        <button className="checkout" disabled={!quote||!!quoteError} onClick={commerce.checkout}>{commerce.user ? 'Continue to checkout' : 'Sign in to checkout'}</button><p className="cart-note">{commerce.user ? 'Your cart is saved on the server. Payments use a local simulator.' : 'Your guest cart stays in this browser. Sign in to save it.'}</p>{commerce.error&&<p className="error" role="alert">{commerce.error}</p>}
      </>}
    </dialog>
    <dialog ref={detailsDialog} className="details-dialog" onCancel={() => setDetails(null)} onClose={() => setDetails(null)} aria-labelledby="product-title">{details && <><button className="icon-button detail-close" aria-label="Close product details" onClick={() => setDetails(null)}><Icon name="close"/></button><img src={`/products/${details.artwork}.svg`} alt={details.name}/><div><p className="eyebrow">{details.category} · {details.badge}</p><h2 id="product-title">{details.name}</h2><p>{details.description}</p><strong>{money(details.priceCents)}</strong><button className="primary" disabled={(cart[details.id] || 0) >= 10} onClick={() => { add(details); setDetails(null); }}>Add to your cart <Icon name="cart"/></button></div></>}</dialog>
    {commerce.ui}
  </>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);

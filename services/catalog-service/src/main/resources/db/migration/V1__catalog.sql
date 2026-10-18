CREATE TABLE products (
    id VARCHAR(40) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    category VARCHAR(40) NOT NULL,
    description VARCHAR(500) NOT NULL,
    price_cents BIGINT NOT NULL CHECK (price_cents > 0),
    currency VARCHAR(3) NOT NULL CHECK (currency = 'USD'),
    artwork VARCHAR(40) NOT NULL,
    badge VARCHAR(40) NOT NULL,
    version BIGINT NOT NULL DEFAULT 1
);
INSERT INTO products (id, name, category, description, price_cents, currency, artwork, badge) VALUES
('bc-001','Cloud Nine Headphones','Tech','The world can wait. Wireless over-ear headphones with a soft fit and a 40-hour soundtrack.',8990,'USD','headphones','Bestseller'),
('bc-002','Main Character Sneakers','Style','A fresh pair for your next plot twist. Cushioned everyday sneakers in warm cream.',7490,'USD','sneakers','New drop'),
('bc-003','Emotional Support Mug','Home','For coffee, tea, and meetings that should have been emails. Ceramic, 350 ml.',1890,'USD','mug','Under $25'),
('bc-004','Touch Grass Backpack','Outdoors','Go somewhere with questionable reception. Water-resistant daypack with generous pockets.',5490,'USD','backpack','Weekend pick'),
('bc-005','Tiny Concert Speaker','Tech','Big main-stage energy in a portable wireless speaker. Up to 12 hours of playback.',3990,'USD','speaker','Fan favorite'),
('bc-006','Do Not Disturb Hoodie','Style','Your official uniform for doing absolutely enough. Heavyweight cotton, relaxed fit.',4990,'USD','hoodie','Cozy club'),
('bc-007','Little Sunshine Lamp','Home','Make your desk a little less Monday. Dimmable warm light with a sculptural silhouette.',3490,'USD','lamp','Mood booster'),
('bc-008','Hydration Situation','Outdoors','A stainless steel bottle for ambitious water goals. Insulated, reusable, 750 ml.',2490,'USD','bottle','Under $25');

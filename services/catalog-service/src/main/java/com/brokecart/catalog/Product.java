package com.brokecart.catalog;
import jakarta.persistence.*;
@Entity
@Table(name = "products")
public class Product {
    @Id private String id;
    private String name;
    private String category;
    private String description;
    private long priceCents;
    private String currency;
    private String artwork;
    private String badge;
    private long version;
    protected Product() {}
    public String getId() { return id; }
    public String getName() { return name; }
    public String getCategory() { return category; }
    public String getDescription() { return description; }
    public long getPriceCents() { return priceCents; }
    public String getCurrency() { return currency; }
    public String getArtwork() { return artwork; }
    public String getBadge() { return badge; }
    public long getVersion() { return version; }
}

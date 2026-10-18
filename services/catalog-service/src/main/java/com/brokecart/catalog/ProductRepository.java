package com.brokecart.catalog;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
interface ProductRepository extends JpaRepository<Product, String> {
    @Query("select p from Product p where (:category = '' or p.category = :category) and (:q = '' or locate(:q, lower(p.name)) > 0 or locate(:q, lower(p.description)) > 0)")
    Page<Product> browse(@Param("category") String category, @Param("q") String q, Pageable pageable);
}

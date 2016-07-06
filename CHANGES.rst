Changelog
=========

1.2.2
-----

- fix post-generation dependencies (olegpidsadnyi)


1.2.1
-----

- automatical resolution of the post-generation dependencies (olegpidsadnyi, kvas-it)


1.1.6
-----

- fixes fixture function module name attribute (olegpidsadnyi)
- fixes _after_postgeneration hook invocation for deferred post-generation declarations (olegpidsadnyi)


1.1.5
-----

- support factory models to be passed as strings (bubenkoff)


1.1.3
-----

- circular dependency determination is fixed for the post-generation (olegpidsadnyi)


1.1.2
-----

- circular dependency determination is fixed for the RelatedFactory attributes (olegpidsadnyi)


1.1.1
-----

- fix installation issue when django environment is not set (bubenkoff, amakhnach)


1.1.0
-----

- fixture dependencies on deferred post-generation declarations (olegpidsadnyi)


1.0.3
-----

- post_generation extra parameters fixed (olegpidsadnyi)
- fixture partial specialization (olegpidsadnyi)
- fixes readme and example (dduong42)
- lazy fixtures (olegpidsadnyi)
- deferred post-generation evaluation (olegpidsadnyi)
- hooks (olegpidsadnyi)


1.0.2
-----

- refactoring of the fixture function compilation (olegpidsadnyi)
- related factory fix (olegpidsadnyi)
- post_generation fixture dependency fixed (olegpidsadnyi)
- model fixture registration with specific name (olegpidsadnyi)
- README updated (olegpidsadnyi)

1.0.1
-----

- use ``inflection`` package to convert camel case to underscore (bubenkoff)

1.0.0
-----

- initial release (olegpidsadnyi)

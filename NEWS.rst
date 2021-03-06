What has changed in I8C?
========================

Changes since I8C 0.0.2
-----------------------

Source language changes
~~~~~~~~~~~~~~~~~~~~~~~

* A new directive "wordsize" has been added to specify the word size
  of the target system in environments where I8C cannot determine it
  automatically.

Note format changes
~~~~~~~~~~~~~~~~~~~

* The byte order mark from the code info chunk has been replaced
  with an architecture specifier which encodes both byte order and
  wordsize.

* All externals table entries now reference functions, and the
  identifying byte at the start of each entry has been removed.
  Additionally, the table is now indexed from 1, with entry 0
  being an implicit reference to the current function.  The
  externals table chunk's version has been incremented to 2 to
  indicate these changes.

Bytecode changes
~~~~~~~~~~~~~~~~

* "extern ptr" statements are now output as DW_OP_addr instructions.

Bug fixes
~~~~~~~~~

* Hexadecimal numbers prefixed with "0X" are now correctly parsed.

Enhancements
~~~~~~~~~~~~

* I8C now supports the use of the environment variables "I8C_CC",
  "I8C_CPP" and "I8C_AS" to specify the external compiler it will
  use.  (https://github.com/gbenson/i8c/issues/13)

Removed features
~~~~~~~~~~~~~~~~

* Support for notes with version 1 signature and code chunks has been
  removed from I8X.


Changes in I8C 0.0.2
--------------------

Source language changes
~~~~~~~~~~~~~~~~~~~~~~~

* Operators with more than one argument now require their arguments to
  be separated by commas.  Existing code using the "name" and "cast"
  operators must be updated.

* Many operators now have an optional ''folded load'' first argument.
  A folded load is exactly equivalent to a load immediately before
  the statement with the folded load, so, for example, this code::

    load 1
    add
    load 5
    bgt label

  may now be written as::

    add 1
    bgt 5, label

  Operators which may have folded loads are:

    * All binary math and logic operators: add, and, div, mod, mul,
      or, shl, shr, shra, sub, xor.

    * All comparisons: eq, ge, gt, le, lt, ne.

    * All conditional branches: beq, bge, bgt, ble, blt, bne.

    * Others: call, deref.

  Operarators which may ''not'' have folded loads are:

    * All unary math and logic operators: abs, neg, not.

    * All stack manipulation operators: drop, dup, over, pick, rot,
      swap.

    * Others: cast, goto, load, name, return.

  The "deref" operator additionally accepts "offset(base)" syntax for
  its optional folded load argument.  This is exactly equivalent to
  two loads and an add, so, for example, this code::

    load base
    load offset
    add
    deref ptr

  may now be written as::

    deref offset(base), ptr

* The "name" operator now accepts slot names as its first argument.
  This can be used to add new names to already-named slots by name.

* Externals are no longer pushed onto the stack at function entry.
  Existing code can be made to work by adding load statements at the
  start of the function, though it's usually possible to eliminate
  some stack manipulation code by rewriting functions with loads where
  they're needed.

* Functions no longer need "extern func" statements to reference
  either themselves or other functions defined in the same file.
  Unnecessary "extern func" statements now result in a warning.

* "extern" statements are now allowed outside of function definitions,
  where they will be inherited by all functions in the same file.

Note format changes
~~~~~~~~~~~~~~~~~~~

* The "max_stack" field from the info chunk and the byteorder mark
  from the code chunk have been moved into a new "code info" chunk
  with a type_id of 5.

* The info chunk now contains only the function's signature.  It has
  been renamed as the signature chunk and its version has been
  incremented to 2 to indicate that the fifth field (if present) is
  not "max_stack".

* The code chunk now contains only bytecode, and externals are no
  longer pushed onto the stack at function entry.  The bytecode
  chunk's version has been incremented to 2 to indicate this.

* "extern ptr" statements now result in symbol reference externals
  table entries.  These have an identifying byte of 's' and contain
  an uleb128 offset into the string table defining the name of the
  referenced symbol.

Bytecode changes
~~~~~~~~~~~~~~~~

* The new wide operation I8_OP_load_external was added to allow
  functions to access externals.

* Dereferencing to integer values is now handled with the new wide
  operation I8_OP_deref_int.

Bug fixes
~~~~~~~~~

* Older versions of unittest are detected and handled in setup.py;
  both the testsuite and I8X should now work out of the box with
  Python 2.6 and 3.1.

* "i8c -S" now outputs to a file unless "-o -" is specified on the
  command line.  (https://github.com/gbenson/i8c/issues/32)

* Stack underflow checks in I8C were off by one in some cases.

* I8C's parser now correctly raises an error if arguments are supplied
  for zero-argument operations.

* I8C's branch-elimination optimizer incorrectly regarded some
  operations as equivalent.  This caused code to be incorrectly
  optimized away in some cases.

* I8X was pushing function arguments in reversed order in some cases.

* I8X incorrectly interpreted operands of comparison operators as
  unsigned values.

Enhancements
~~~~~~~~~~~~

* I8C's branch-elimination optimizer now recognizes that "dup" and
  "over" are equivalents of "pick 0" and "pick 1" respectively.

* Warnings are now issued for unreachable code.

* There is the start of an Emacs major mode in "contrib/i8-mode.el".

* I8C's optimizer now combines equivalent basic blocks.

* I8X can now accept functions and opaque values in function argument
  lists supplied by testcases.

* I8X now has a system which testcases may use to lay out test address
  spaces to check memory accesses using "deref" et al.

#include "test-input-2.h"

class A {
    int a;
public:
    A() {}
    A(int a) : a(a) {}
    ~A() {}
    A(const A&) = delete;
    A(A&&) = delete;
};

class B {
    int b;
public:
    B() = default;
    B(int b) : b(b) {}
    ~B() noexcept {}
    B(const B&) = default;
    B(B&&) = default;
};

class C {
    int c;
// no explicit constructor
};
#include "example-2.h"

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

// func decl
float func(float, float *, int arr[]);
char returnChar_takeFunc1(float (*func)(float, float *));
typedef float (*FuncPtrTy)(float, float *);
char returnChar_takeFunc2(FuncPtrTy func);
// var decl
float (*funcPtr1)(float, float *);
FuncPtrTy funcPtr2;
#include <vector>
#include <unordered_map>

/**
 * comment for NS
 */
namespace NS {
class Complex {
private:
    double re;
    double im;
public:
    Complex() : re(0), im(0) {}
    Complex(double re, double im) : re(re), im(im) {}
    Complex(Complex &&) = delete;
    /**
     * Usage: bool b = complex.isReal();
     * -----------------
     * comment for isReal()
     */
    bool isReal() const {
        return im == 0;
    }
    Complex &operator+=(Complex &&);
};

std::vector<Complex> independentFunction(std::vector<Complex> &v1, double);

enum E1 : char { e11, e12 };
enum class E2 : long { e21 = 2, e22 };

class Aother {
public:
    enum class E { e1, e2 };
};

template <typename T, int N>
void fooTemplated(bool b, Complex &c);

template <typename T, typename U>
class BarTemplated {
public:
    T t_;
    U u_;
    int a;
};

class Class2 {
public:
    typedef int Class2Int;

};

template <typename T1, typename T2>
class Class3Templated {
    using TT = T2;
    class Class3Mid {
        template <unsigned N, typename U>
        class Class3InnerTemplated {
            U u1_;
            using UU = U;
            UU u2_;
        };
    };
    TT tt_;
};

typedef Class2 Class2Ty;
using Class2Ty2 = Class2Ty;

Class2Ty::Class2Int var1;
Class2Ty2::Class2Int var2;

using Float = float;
Float var3;

using Float2 = Float;
Float2 var4;
}
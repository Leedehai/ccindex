#include <vector>

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
void foo(bool b, Complex &c);

template <typename T, typename U>
class Bar {
public:
    T t_;
    U u_;
    int a;
};

}
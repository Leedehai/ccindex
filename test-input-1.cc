// this is a test input with grammar errors
#include <vector>
#include <map>
using namespace std;

const int independentVariable = 1;
int independentFunction();
typedef std::vector<int> Int;

/** comment for MyClass */
class MyClass {
	int property1;
	static void method1();
public:
	/** comment for MyClass() */
	MyClass();
	MyClass(const MyClass &);
	MyClass(int a, Int b) : property2(a) {} /*< comment for MyClass(int, Int) */
	Int method2();
	MyClass(MyClass &&);
	MyClass operator+(const MyClass &);
	operator int();
private:
	/** comment for property2 */
	Int property2;
	/**
	 * comment for property 3
	 * still comment for property 3
	 */
	const float propertye3;

	class InnerClass {
		double b;
	};

	virtual void method3() const = 0;
};

// non-doc comment
int baz();

/* non-doc comment */
template <typename T, typename U=Int, int N=1>
int templateFunc(T *pt, U *pu, int n=N);

/** comment for foo() */
int foo(int a, Int b);

// function bodies are skipped
MyClass::MyClass(int a, Int b) {
	int aa = a;
	Int bb = b;
}

namespace NS2 {
/* class template */
template <typename T, char C>
class templateClass {
	T t_;
	char c_ = C;
};
}

enum E : int {
	a = 1,
	b
};

/** comment for namespace */
namespace customNS {
	int foo();
	class Class;
}

static int staticGlobal;

class customNS::Class final {
	static int staticData;
	const int constData;
	static const int staticConstData;
	int b;
friend class classFriend;
friend int fooFriend();
size_t returnSizeT_int(int a);
bool returnBool_string_myclass_anotherclass(string s, MyClass obj, Another obj2);
std::vector<int> &returnVector_float_vector(float a, std::vector<int> b);
};

class classFriend {};
int fooFriend();

int a1, *a2;
std::map<int, int> m;

int foo() {
	int aaa = 0;
	return aaa;
}

Another ano;
struct EEClass {
	enum class EE : char { ee1, ee2 };
};
typedef enum { eee1, eee2 } EnumTy;
enum { aaaaa, bbbbb };

class BaseClass {};
template <typename T>
struct BaseClass2 {};
template <typename T>
class ClassAgain {};

class VClass final
: private BaseClass, BaseClass2<ClassAgain<int>>, public virtual EEClass {
public:
    VClass();
    virtual ~VClass() = 0;
    virtual void foo() = 0;
};

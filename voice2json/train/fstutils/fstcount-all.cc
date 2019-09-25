#include <fst/fst.h>

unsigned long countAll(const fst::StdFst& fst,
                       const fst::StdArc::StateId state) {

  unsigned long count = 0;
  for (fst::ArcIterator<fst::StdFst> aiter(fst, state);
       !aiter.Done();
       aiter.Next()) {
    const fst::StdArc &arc = aiter.Value();
    // path.push_back(arc);

    if (fst.Final(arc.nextstate) != fst::StdArc::Weight::Zero()) {
      count += 1;
    } else {
      count += countAll(fst, arc.nextstate);
    }
  }

  return count;
}

int main(int argc, char** argv) {
  if (argc < 2) {
    std::cerr << "Usage: fstcount-all FST" << std::endl;
    return 1;
  }

  std::string in_filename(argv[1]);
  const fst::StdFst *in_fst =
      fst::StdFst::Read(in_filename);

  const auto startState = in_fst->Start();
  std::cout << countAll(*in_fst, startState) << std::endl;

  return 0;
}

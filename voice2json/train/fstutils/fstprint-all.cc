#include <fst/fst.h>

void printAll(const fst::StdFst& fst,
              const fst::StdArc::StateId state,
              std::vector<fst::StdArc> path) {

  for (fst::ArcIterator<fst::StdFst> aiter(fst, state);
       !aiter.Done();
       aiter.Next()) {
    const fst::StdArc &arc = aiter.Value();
    path.push_back(arc);

    if (fst.Final(arc.nextstate) != fst::StdArc::Weight::Zero()) {
      for (size_t i = 0; i < path.size(); ++i) {
        if (path[i].olabel != 0) {  // assume <eps> is 0
          std::cout << fst.OutputSymbols()->Find(path[i].olabel) << " ";
        }
      }
      std::cout << std::endl;
    } else {
      printAll(fst, arc.nextstate, path);
    }

    path.pop_back();
  }
}

int main(int argc, char** argv) {
  if (argc < 2) {
    std::cerr << "Usage: fstprint-all FST" << std::endl;
    return 1;
  }

  std::string in_filename(argv[1]);
  const fst::StdFst *in_fst =
      fst::StdFst::Read(in_filename);

  const auto startState = in_fst->Start();
  std::vector<fst::StdArc> path;
  printAll(*in_fst, startState, path);

  return 0;
}

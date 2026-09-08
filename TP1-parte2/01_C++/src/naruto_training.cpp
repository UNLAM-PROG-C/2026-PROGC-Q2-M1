#include <chrono>
#include <cstdlib>
#include <iostream>
#include <random>
#include <thread>
#include <vector>

namespace
{
    constexpr int MIN_CHAKRA = 5;
    constexpr int MAX_CHAKRA = 10;
    constexpr int MIN_ATTEMPT_MS = 100;
    constexpr int MAX_ATTEMPT_MS = 200;
    constexpr double LEVEL_UP_PROBABILITY = 0.5;
}


void trainClone(int cloneId, unsigned int seed, int &levelOut)
{
    std::mt19937 rng(seed);
    std::uniform_int_distribution<int> chakraDist(MIN_CHAKRA, MAX_CHAKRA);
    std::uniform_int_distribution<int> attemptDurationDist(MIN_ATTEMPT_MS, MAX_ATTEMPT_MS);
    std::uniform_real_distribution<double> successDist(0.0, 1.0);

    int chakra = chakraDist(rng);
    int level = 0;

    for (int attempt = 0; attempt < chakra; ++attempt)
    {
        std::this_thread::sleep_for(std::chrono::milliseconds(attemptDurationDist(rng)));

        if (successDist(rng) < LEVEL_UP_PROBABILITY)
        {
            ++level;
        }
    }

    levelOut = level;
    (void)cloneId;
}

int main(int argc, char *argv[])
{
    int numClones = 10;
    if (argc > 1)
    {
        numClones = std::atoi(argv[1]);
    }
    if (numClones <= 0)
    {
        std::cerr << "La cantidad de clones debe ser un entero positivo." << std::endl;
        return 1;
    }

    std::random_device rd;
    std::mt19937 seedGenerator(rd());
    std::vector<unsigned int> seeds(numClones);
    for (int i = 0; i < numClones; ++i)
    {
        seeds[i] = seedGenerator();
    }

    std::vector<int> levels(numClones, 0);
    std::vector<std::thread> clones;
    clones.reserve(numClones);

    auto start = std::chrono::steady_clock::now();

    for (int i = 0; i < numClones; ++i)
    {
        clones.emplace_back(trainClone, i, seeds[i], std::ref(levels[i]));
    }

    for (auto &clone : clones)
    {
        clone.join();
    }

    auto end = std::chrono::steady_clock::now();
    auto elapsedMs = std::chrono::duration_cast<std::chrono::milliseconds>(end - start).count();

    int totalLevel = 0;
    for (int i = 0; i < numClones; ++i)
    {
        std::cout << "Clon " << i << ": nivel alcanzado = " << levels[i] << std::endl;
        totalLevel += levels[i];
    }

    std::cout << "----" << std::endl;
    std::cout << "Clones: " << numClones << std::endl;
    std::cout << "Nivel total ganado por Naruto: " << totalLevel << std::endl;
    std::cout << "Tiempo total: " << elapsedMs << " ms" << std::endl;

    return 0;
}

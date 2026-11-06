"""Standardized Diverse Benchmark Corpus for Model Capability & Neural Fine-Tuning Evaluation.

Contains 160 distinct, realistic problems across 8 core domains:
1. Arrays & Sorting (20 problems)
2. Strings & Two Pointers (20 problems)
3. Stack & Queue (20 problems)
4. Trees, Graphs & Recursion (20 problems)
5. Dynamic Programming (20 problems)
6. Math & Number Theory (20 problems)
7. Hash Maps & Sets (20 problems)
8. Schema & Protocol Contracts (20 problems)

Each problem includes:
- id: Canonical task identifier
- category: "code" | "math" | "schema"
- domain: Specific engineering domain
- prompt: Clear instruction with function signature and constraints
- reference_solution: Mathematically & logically correct reference code or JSON
- hidden_tests: Private test assertions evaluated in the native sandbox
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def build_benchmark_corpus() -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []

    # =========================================================================
    # 1. ARRAYS & SORTING (20 problems)
    # =========================================================================
    tasks.append({
        "id": "bench_arr_01_two_sum_sorted",
        "category": "code",
        "domain": "arrays_sorting",
        "prompt": "Implement two_sum_sorted(numbers: list, target: int) -> list returning 1-based indices of two numbers that add up to target.",
        "reference_solution": (
            "def two_sum_sorted(numbers: list, target: int) -> list:\n"
            "    left, right = 0, len(numbers) - 1\n"
            "    while left < right:\n"
            "        s = numbers[left] + numbers[right]\n"
            "        if s == target:\n"
            "            return [left + 1, right + 1]\n"
            "        elif s < target:\n"
            "            left += 1\n"
            "        else:\n"
            "            right -= 1\n"
            "    return []\n"
        ),
        "hidden_tests": "assert two_sum_sorted([2, 7, 11, 15], 9) == [1, 2]\nassert two_sum_sorted([2, 3, 4], 6) == [1, 3]\nassert two_sum_sorted([-1, 0], -1) == [1, 2]",
    })

    tasks.append({
        "id": "bench_arr_02_majority_element",
        "category": "code",
        "domain": "arrays_sorting",
        "prompt": "Implement majority_element(nums: list) -> int returning element appearing more than n // 2 times using Boyer-Moore Voting.",
        "reference_solution": (
            "def majority_element(nums: list) -> int:\n"
            "    count = 0\n"
            "    candidate = None\n"
            "    for x in nums:\n"
            "        if count == 0:\n"
            "            candidate = x\n"
            "        count += (1 if x == candidate else -1)\n"
            "    return candidate\n"
        ),
        "hidden_tests": "assert majority_element([3, 2, 3]) == 3\nassert majority_element([2, 2, 1, 1, 1, 2, 2]) == 2\nassert majority_element([1]) == 1",
    })

    tasks.append({
        "id": "bench_arr_03_max_subarray_kadane",
        "category": "code",
        "domain": "arrays_sorting",
        "prompt": "Implement max_subarray(nums: list) -> int returning maximum sum of a contiguous subarray using Kadane's algorithm.",
        "reference_solution": (
            "def max_subarray(nums: list) -> int:\n"
            "    if not nums: return 0\n"
            "    curr = max_sum = nums[0]\n"
            "    for x in nums[1:]:\n"
            "        curr = max(x, curr + x)\n"
            "        max_sum = max(max_sum, curr)\n"
            "    return max_sum\n"
        ),
        "hidden_tests": "assert max_subarray([-2, 1, -3, 4, -1, 2, 1, -5, 4]) == 6\nassert max_subarray([1]) == 1\nassert max_subarray([5, 4, -1, 7, 8]) == 23",
    })

    tasks.append({
        "id": "bench_arr_04_move_zeroes",
        "category": "code",
        "domain": "arrays_sorting",
        "prompt": "Implement move_zeroes(nums: list) -> list moving all 0's to end while maintaining relative order of non-zero elements.",
        "reference_solution": (
            "def move_zeroes(nums: list) -> list:\n"
            "    res = [x for x in nums if x != 0]\n"
            "    res.extend([0] * (len(nums) - len(res)))\n"
            "    return res\n"
        ),
        "hidden_tests": "assert move_zeroes([0, 1, 0, 3, 12]) == [1, 3, 12, 0, 0]\nassert move_zeroes([0]) == [0]\nassert move_zeroes([4, 2, 4, 0, 0, 3, 0, 5, 1, 0]) == [4, 2, 4, 3, 5, 1, 0, 0, 0, 0]",
    })

    tasks.append({
        "id": "bench_arr_05_dutch_national_flag",
        "category": "code",
        "domain": "arrays_sorting",
        "prompt": "Implement sort_colors(nums: list) -> list sorting an array with values 0, 1, and 2 in-place or returning sorted list.",
        "reference_solution": (
            "def sort_colors(nums: list) -> list:\n"
            "    arr = list(nums)\n"
            "    low, mid, high = 0, 0, len(arr) - 1\n"
            "    while mid <= high:\n"
            "        if arr[mid] == 0:\n"
            "            arr[low], arr[mid] = arr[mid], arr[low]\n"
            "            low += 1; mid += 1\n"
            "        elif arr[mid] == 1:\n"
            "            mid += 1\n"
            "        else:\n"
            "            arr[mid], arr[high] = arr[high], arr[mid]\n"
            "            high -= 1\n"
            "    return arr\n"
        ),
        "hidden_tests": "assert sort_colors([2, 0, 2, 1, 1, 0]) == [0, 0, 1, 1, 2, 2]\nassert sort_colors([2, 0, 1]) == [0, 1, 2]\nassert sort_colors([0]) == [0]",
    })

    tasks.append({
        "id": "bench_arr_06_rotate_array",
        "category": "code",
        "domain": "arrays_sorting",
        "prompt": "Implement rotate_array(nums: list, k: int) -> list rotating array to the right by k steps.",
        "reference_solution": (
            "def rotate_array(nums: list, k: int) -> list:\n"
            "    if not nums: return []\n"
            "    n = len(nums)\n"
            "    k = k % n\n"
            "    return nums[-k:] + nums[:-k] if k > 0 else list(nums)\n"
        ),
        "hidden_tests": "assert rotate_array([1, 2, 3, 4, 5, 6, 7], 3) == [5, 6, 7, 1, 2, 3, 4]\nassert rotate_array([-1, -100, 3, 99], 2) == [3, 99, -1, -100]\nassert rotate_array([1, 2], 3) == [2, 1]",
    })

    tasks.append({
        "id": "bench_arr_07_find_peak_element",
        "category": "code",
        "domain": "arrays_sorting",
        "prompt": "Implement find_peak_element(nums: list) -> int returning index of any peak element (strictly greater than neighbors).",
        "reference_solution": (
            "def find_peak_element(nums: list) -> int:\n"
            "    low, high = 0, len(nums) - 1\n"
            "    while low < high:\n"
            "        mid = (low + high) // 2\n"
            "        if nums[mid] > nums[mid + 1]:\n"
            "            high = mid\n"
            "        else:\n"
            "            low = mid + 1\n"
            "    return low\n"
        ),
        "hidden_tests": "assert find_peak_element([1, 2, 3, 1]) == 2\nassert find_peak_element([1, 2, 1, 3, 5, 6, 4]) in (1, 5)\nassert find_peak_element([1]) == 0",
    })

    tasks.append({
        "id": "bench_arr_08_merge_sorted_arrays",
        "category": "code",
        "domain": "arrays_sorting",
        "prompt": "Implement merge_sorted(a: list, b: list) -> list merging two sorted lists into one sorted list in O(n+m).",
        "reference_solution": (
            "def merge_sorted(a: list, b: list) -> list:\n"
            "    i = j = 0\n"
            "    res = []\n"
            "    while i < len(a) and j < len(b):\n"
            "        if a[i] <= b[j]:\n"
            "            res.append(a[i]); i += 1\n"
            "        else:\n"
            "            res.append(b[j]); j += 1\n"
            "    res.extend(a[i:])\n"
            "    res.extend(b[j:])\n"
            "    return res\n"
        ),
        "hidden_tests": "assert merge_sorted([1, 3, 5], [2, 4, 6]) == [1, 2, 3, 4, 5, 6]\nassert merge_sorted([], [1, 2]) == [1, 2]\nassert merge_sorted([5], []) == [5]",
    })

    tasks.append({
        "id": "bench_arr_09_product_except_self",
        "category": "code",
        "domain": "arrays_sorting",
        "prompt": "Implement product_except_self(nums: list) -> list returning array where out[i] equals product of all elements except nums[i].",
        "reference_solution": (
            "def product_except_self(nums: list) -> list:\n"
            "    n = len(nums)\n"
            "    res = [1] * n\n"
            "    p = 1\n"
            "    for i in range(n):\n"
            "        res[i] = p\n"
            "        p *= nums[i]\n"
            "    p = 1\n"
            "    for i in range(n - 1, -1, -1):\n"
            "        res[i] *= p\n"
            "        p *= nums[i]\n"
            "    return res\n"
        ),
        "hidden_tests": "assert product_except_self([1, 2, 3, 4]) == [24, 12, 8, 6]\nassert product_except_self([-1, 1, 0, -3, 3]) == [0, 0, 9, 0, 0]",
    })

    tasks.append({
        "id": "bench_arr_10_missing_number",
        "category": "code",
        "domain": "arrays_sorting",
        "prompt": "Implement missing_number(nums: list) -> int finding the only number in range [0, n] missing from array.",
        "reference_solution": (
            "def missing_number(nums: list) -> int:\n"
            "    n = len(nums)\n"
            "    return (n * (n + 1)) // 2 - sum(nums)\n"
        ),
        "hidden_tests": "assert missing_number([3, 0, 1]) == 2\nassert missing_number([0, 1]) == 2\nassert missing_number([9, 6, 4, 2, 3, 5, 7, 0, 1]) == 8",
    })

    tasks.append({
        "id": "bench_arr_11_container_most_water",
        "category": "code",
        "domain": "arrays_sorting",
        "prompt": "Implement max_area(height: list) -> int finding two lines together with x-axis forming container holding max water.",
        "reference_solution": (
            "def max_area(height: list) -> int:\n"
            "    left, right = 0, len(height) - 1\n"
            "    max_w = 0\n"
            "    while left < right:\n"
            "        w = (right - left) * min(height[left], height[right])\n"
            "        if w > max_w: max_w = w\n"
            "        if height[left] < height[right]: left += 1\n"
            "        else: right -= 1\n"
            "    return max_w\n"
        ),
        "hidden_tests": "assert max_area([1, 8, 6, 2, 5, 4, 8, 3, 7]) == 49\nassert max_area([1, 1]) == 1\nassert max_area([4, 3, 2, 1, 4]) == 16",
    })

    tasks.append({
        "id": "bench_arr_12_remove_duplicates_sorted",
        "category": "code",
        "domain": "arrays_sorting",
        "prompt": "Implement remove_duplicates_sorted(nums: list) -> list removing duplicates from sorted array returning deduplicated list.",
        "reference_solution": (
            "def remove_duplicates_sorted(nums: list) -> list:\n"
            "    if not nums: return []\n"
            "    res = [nums[0]]\n"
            "    for x in nums[1:]:\n"
            "        if x != res[-1]: res.append(x)\n"
            "    return res\n"
        ),
        "hidden_tests": "assert remove_duplicates_sorted([1, 1, 2]) == [1, 2]\nassert remove_duplicates_sorted([0, 0, 1, 1, 1, 2, 2, 3, 3, 4]) == [0, 1, 2, 3, 4]\nassert remove_duplicates_sorted([]) == []",
    })

    tasks.append({
        "id": "bench_arr_13_merge_intervals",
        "category": "code",
        "domain": "arrays_sorting",
        "prompt": "Implement merge_intervals(intervals: list) -> list merging overlapping intervals.",
        "reference_solution": (
            "def merge_intervals(intervals: list) -> list:\n"
            "    if not intervals: return []\n"
            "    intervals = sorted(intervals, key=lambda x: x[0])\n"
            "    merged = [intervals[0]]\n"
            "    for cur in intervals[1:]:\n"
            "        prev = merged[-1]\n"
            "        if cur[0] <= prev[1]:\n"
            "            merged[-1] = [prev[0], max(prev[1], cur[1])]\n"
            "        else:\n"
            "            merged.append(cur)\n"
            "    return merged\n"
        ),
        "hidden_tests": "assert merge_intervals([[1, 3], [2, 6], [8, 10], [15, 18]]) == [[1, 6], [8, 10], [15, 18]]\nassert merge_intervals([[1, 4], [4, 5]]) == [[1, 5]]\nassert merge_intervals([]) == []",
    })

    tasks.append({
        "id": "bench_arr_14_search_rotated_sorted",
        "category": "code",
        "domain": "arrays_sorting",
        "prompt": "Implement search_rotated(nums: list, target: int) -> int returning index of target in rotated sorted array or -1.",
        "reference_solution": (
            "def search_rotated(nums: list, target: int) -> int:\n"
            "    lo, hi = 0, len(nums) - 1\n"
            "    while lo <= hi:\n"
            "        mid = (lo + hi) // 2\n"
            "        if nums[mid] == target: return mid\n"
            "        if nums[lo] <= nums[mid]:\n"
            "            if nums[lo] <= target < nums[mid]: hi = mid - 1\n"
            "            else: lo = mid + 1\n"
            "        else:\n"
            "            if nums[mid] < target <= nums[hi]: lo = mid + 1\n"
            "            else: hi = mid - 1\n"
            "    return -1\n"
        ),
        "hidden_tests": "assert search_rotated([4, 5, 6, 7, 0, 1, 2], 0) == 4\nassert search_rotated([4, 5, 6, 7, 0, 1, 2], 3) == -1\nassert search_rotated([1], 0) == -1",
    })

    tasks.append({
        "id": "bench_arr_15_find_disappeared_numbers",
        "category": "code",
        "domain": "arrays_sorting",
        "prompt": "Implement find_disappeared(nums: list) -> list returning list of numbers in [1, n] not in nums.",
        "reference_solution": (
            "def find_disappeared(nums: list) -> list:\n"
            "    s = set(nums)\n"
            "    return [i for i in range(1, len(nums) + 1) if i not in s]\n"
        ),
        "hidden_tests": "assert find_disappeared([4, 3, 2, 7, 8, 2, 3, 1]) == [5, 6]\nassert find_disappeared([1, 1]) == [2]",
    })

    tasks.append({
        "id": "bench_arr_16_intersection_arrays",
        "category": "code",
        "domain": "arrays_sorting",
        "prompt": "Implement intersection(nums1: list, nums2: list) -> list returning unique elements appearing in both arrays sorted.",
        "reference_solution": (
            "def intersection(nums1: list, nums2: list) -> list:\n"
            "    return sorted(list(set(nums1) & set(nums2)))\n"
        ),
        "hidden_tests": "assert intersection([1, 2, 2, 1], [2, 2]) == [2]\nassert intersection([4, 9, 5], [9, 4, 9, 8, 4]) == [4, 9]",
    })

    tasks.append({
        "id": "bench_arr_17_summary_ranges",
        "category": "code",
        "domain": "arrays_sorting",
        "prompt": "Implement summary_ranges(nums: list) -> list returning smallest sorted list of ranges covering all numbers.",
        "reference_solution": (
            "def summary_ranges(nums: list) -> list:\n"
            "    if not nums: return []\n"
            "    res = []\n"
            "    start = nums[0]\n"
            "    for i in range(1, len(nums) + 1):\n"
            "        if i == len(nums) or nums[i] != nums[i - 1] + 1:\n"
            "            if start == nums[i - 1]: res.append(str(start))\n"
            "            else: res.append(f'{start}->{nums[i-1]}')\n"
            "            if i < len(nums): start = nums[i]\n"
            "    return res\n"
        ),
        "hidden_tests": "assert summary_ranges([0, 1, 2, 4, 5, 7]) == ['0->2', '4->5', '7']\nassert summary_ranges([0, 2, 3, 4, 6, 8, 9]) == ['0', '2->4', '6', '8->9']",
    })

    tasks.append({
        "id": "bench_arr_18_three_sum_zero",
        "category": "code",
        "domain": "arrays_sorting",
        "prompt": "Implement three_sum(nums: list) -> list returning all unique triplets [nums[i], nums[j], nums[k]] that sum to 0.",
        "reference_solution": (
            "def three_sum(nums: list) -> list:\n"
            "    nums.sort()\n"
            "    res = []\n"
            "    for i in range(len(nums) - 2):\n"
            "        if i > 0 and nums[i] == nums[i - 1]: continue\n"
            "        l, r = i + 1, len(nums) - 1\n"
            "        while l < r:\n"
            "            s = nums[i] + nums[l] + nums[r]\n"
            "            if s < 0: l += 1\n"
            "            elif s > 0: r -= 1\n"
            "            else:\n"
            "                res.append([nums[i], nums[l], nums[r]])\n"
            "                while l < r and nums[l] == nums[l + 1]: l += 1\n"
            "                while l < r and nums[r] == nums[r - 1]: r -= 1\n"
            "                l += 1; r -= 1\n"
            "    return res\n"
        ),
        "hidden_tests": "assert three_sum([-1, 0, 1, 2, -1, -4]) == [[-1, -1, 2], [-1, 0, 1]]\nassert three_sum([0, 1, 1]) == []\nassert three_sum([0, 0, 0]) == [[0, 0, 0]]",
    })

    tasks.append({
        "id": "bench_arr_19_spiral_matrix",
        "category": "code",
        "domain": "arrays_sorting",
        "prompt": "Implement spiral_order(matrix: list) -> list returning elements of matrix in spiral order.",
        "reference_solution": (
            "def spiral_order(matrix: list) -> list:\n"
            "    if not matrix or not matrix[0]: return []\n"
            "    res = []\n"
            "    top, bot = 0, len(matrix) - 1\n"
            "    left, right = 0, len(matrix[0]) - 1\n"
            "    while top <= bot and left <= right:\n"
            "        for c in range(left, right + 1): res.append(matrix[top][c])\n"
            "        top += 1\n"
            "        for r in range(top, bot + 1): res.append(matrix[r][right])\n"
            "        right -= 1\n"
            "        if top <= bot:\n"
            "            for c in range(right, left - 1, -1): res.append(matrix[bot][c])\n"
            "            bot -= 1\n"
            "        if left <= right:\n"
            "            for r in range(bot, top - 1, -1): res.append(matrix[r][left])\n"
            "            left += 1\n"
            "    return res\n"
        ),
        "hidden_tests": "assert spiral_order([[1, 2, 3], [4, 5, 6], [7, 8, 9]]) == [1, 2, 3, 6, 9, 8, 7, 4, 5]\nassert spiral_order([[1, 2], [3, 4]]) == [1, 2, 4, 3]",
    })

    tasks.append({
        "id": "bench_arr_20_insert_interval",
        "category": "code",
        "domain": "arrays_sorting",
        "prompt": "Implement insert_interval(intervals: list, new_interval: list) -> list inserting new_interval into sorted intervals and merging.",
        "reference_solution": (
            "def insert_interval(intervals: list, new_interval: list) -> list:\n"
            "    res = []\n"
            "    i = 0\n"
            "    n = len(intervals)\n"
            "    while i < n and intervals[i][1] < new_interval[0]:\n"
            "        res.append(intervals[i]); i += 1\n"
            "    while i < n and intervals[i][0] <= new_interval[1]:\n"
            "        new_interval = [min(new_interval[0], intervals[i][0]), max(new_interval[1], intervals[i][1])]\n"
            "        i += 1\n"
            "    res.append(new_interval)\n"
            "    while i < n: res.append(intervals[i]); i += 1\n"
            "    return res\n"
        ),
        "hidden_tests": "assert insert_interval([[1, 3], [6, 9]], [2, 5]) == [[1, 5], [6, 9]]\nassert insert_interval([[1, 2], [3, 5], [6, 7], [8, 10], [12, 16]], [4, 8]) == [[1, 2], [3, 10], [12, 16]]",
    })

    # =========================================================================
    # 2. STRINGS & TWO POINTERS (20 problems)
    # =========================================================================
    tasks.append({
        "id": "bench_str_01_longest_palindrome_substr",
        "category": "code",
        "domain": "strings_two_pointers",
        "prompt": "Implement longest_palindrome(s: str) -> str finding the longest palindromic substring in s.",
        "reference_solution": (
            "def longest_palindrome(s: str) -> str:\n"
            "    if not s: return ''\n"
            "    start, end = 0, 0\n"
            "    def expand(left, right):\n"
            "        while left >= 0 and right < len(s) and s[left] == s[right]:\n"
            "            left -= 1; right += 1\n"
            "        return left + 1, right - 1\n"
            "    for i in range(len(s)):\n"
            "        l1, r1 = expand(i, i)\n"
            "        l2, r2 = expand(i, i + 1)\n"
            "        if r1 - l1 > end - start: start, end = l1, r1\n"
            "        if r2 - l2 > end - start: start, end = l2, r2\n"
            "    return s[start:end+1]\n"
        ),
        "hidden_tests": "assert longest_palindrome('babad') in ('bab', 'aba')\nassert longest_palindrome('cbbd') == 'bb'\nassert longest_palindrome('a') == 'a'",
    })

    tasks.append({
        "id": "bench_str_02_valid_anagram",
        "category": "code",
        "domain": "strings_two_pointers",
        "prompt": "Implement is_anagram(s: str, t: str) -> bool returning True if t is an anagram of s.",
        "reference_solution": (
            "def is_anagram(s: str, t: str) -> bool:\n"
            "    if len(s) != len(t): return False\n"
            "    from collections import Counter\n"
            "    return Counter(s) == Counter(t)\n"
        ),
        "hidden_tests": "assert is_anagram('anagram', 'nagaram') == True\nassert is_anagram('rat', 'car') == False\nassert is_anagram('', '') == True",
    })

    tasks.append({
        "id": "bench_str_03_group_anagrams",
        "category": "code",
        "domain": "strings_two_pointers",
        "prompt": "Implement group_anagrams(strs: list) -> list grouping anagrams together sorted by group length.",
        "reference_solution": (
            "def group_anagrams(strs: list) -> list:\n"
            "    from collections import defaultdict\n"
            "    groups = defaultdict(list)\n"
            "    for s in strs:\n"
            "        key = ''.join(sorted(s))\n"
            "        groups[key].append(s)\n"
            "    return sorted(list(groups.values()), key=lambda g: (len(g), g[0] if g else ''))\n"
        ),
        "hidden_tests": "res = group_anagrams(['eat', 'tea', 'tan', 'ate', 'nat', 'bat'])\nassert len(res) == 3\nassert any('bat' in g for g in res)",
    })

    tasks.append({
        "id": "bench_str_04_string_compression",
        "category": "code",
        "domain": "strings_two_pointers",
        "prompt": "Implement compress_string(chars: list) -> str returning run-length compressed string if shorter, else original.",
        "reference_solution": (
            "def compress_string(chars: list) -> str:\n"
            "    if not chars: return ''\n"
            "    res = []\n"
            "    i = 0\n"
            "    while i < len(chars):\n"
            "        c = chars[i]\n"
            "        count = 0\n"
            "        while i < len(chars) and chars[i] == c:\n"
            "            count += 1; i += 1\n"
            "        res.append(c + (str(count) if count > 1 else ''))\n"
            "    return ''.join(res)\n"
        ),
        "hidden_tests": "assert compress_string(['a', 'a', 'b', 'b', 'c', 'c', 'c']) == 'a2b2c3'\nassert compress_string(['a']) == 'a'",
    })

    tasks.append({
        "id": "bench_str_05_reverse_vowels",
        "category": "code",
        "domain": "strings_two_pointers",
        "prompt": "Implement reverse_vowels(s: str) -> str reversing only all the vowels in the string.",
        "reference_solution": (
            "def reverse_vowels(s: str) -> str:\n"
            "    vowels = set('aeiouAEIOU')\n"
            "    arr = list(s)\n"
            "    l, r = 0, len(arr) - 1\n"
            "    while l < r:\n"
            "        while l < r and arr[l] not in vowels: l += 1\n"
            "        while l < r and arr[r] not in vowels: r -= 1\n"
            "        arr[l], arr[r] = arr[r], arr[l]\n"
            "        l += 1; r -= 1\n"
            "    return ''.join(arr)\n"
        ),
        "hidden_tests": "assert reverse_vowels('hello') == 'holle'\nassert reverse_vowels('leetcode') == 'leotcede'",
    })

    tasks.append({
        "id": "bench_str_06_longest_common_prefix",
        "category": "code",
        "domain": "strings_two_pointers",
        "prompt": "Implement longest_common_prefix(strs: list) -> str finding the longest common prefix among strings.",
        "reference_solution": (
            "def longest_common_prefix(strs: list) -> str:\n"
            "    if not strs: return ''\n"
            "    prefix = strs[0]\n"
            "    for s in strs[1:]:\n"
            "        while not s.startswith(prefix):\n"
            "            prefix = prefix[:-1]\n"
            "            if not prefix: return ''\n"
            "    return prefix\n"
        ),
        "hidden_tests": "assert longest_common_prefix(['flower', 'flow', 'flight']) == 'fl'\nassert longest_common_prefix(['dog', 'racecar', 'car']) == ''",
    })

    tasks.append({
        "id": "bench_str_07_valid_palindrome_remove_one",
        "category": "code",
        "domain": "strings_two_pointers",
        "prompt": "Implement valid_palindrome_remove_one(s: str) -> bool returning True if s can be a palindrome after deleting at most one character.",
        "reference_solution": (
            "def valid_palindrome_remove_one(s: str) -> bool:\n"
            "    def is_p(sub): return sub == sub[::-1]\n"
            "    l, r = 0, len(s) - 1\n"
            "    while l < r:\n"
            "        if s[l] != s[r]:\n"
            "            return is_p(s[l:r]) or is_p(s[l+1:r+1])\n"
            "        l += 1; r -= 1\n"
            "    return True\n"
        ),
        "hidden_tests": "assert valid_palindrome_remove_one('aba') == True\nassert valid_palindrome_remove_one('abca') == True\nassert valid_palindrome_remove_one('abc') == False",
    })

    tasks.append({
        "id": "bench_str_08_run_length_encode",
        "category": "code",
        "domain": "strings_two_pointers",
        "prompt": "Implement run_length_encode(s: str) -> str encoding consecutive repeating characters into char + count.",
        "reference_solution": (
            "def run_length_encode(s: str) -> str:\n"
            "    if not s: return ''\n"
            "    res = []\n"
            "    count = 1\n"
            "    for i in range(1, len(s)):\n"
            "        if s[i] == s[i - 1]: count += 1\n"
            "        else:\n"
            "            res.append(f'{s[i-1]}{count}')\n"
            "            count = 1\n"
            "    res.append(f'{s[-1]}{count}')\n"
            "    return ''.join(res)\n"
        ),
        "hidden_tests": "assert run_length_encode('WWWWWWAAAA') == 'W6A4'\nassert run_length_encode('A') == 'A1'\nassert run_length_encode('') == ''",
    })

    tasks.append({
        "id": "bench_str_09_reverse_words",
        "category": "code",
        "domain": "strings_two_pointers",
        "prompt": "Implement reverse_words(s: str) -> str reversing word order with single whitespace separation.",
        "reference_solution": (
            "def reverse_words(s: str) -> str:\n"
            "    return ' '.join((s or '').split()[::-1])\n"
        ),
        "hidden_tests": "assert reverse_words('the sky is blue') == 'blue is sky the'\nassert reverse_words('  hello world  ') == 'world hello'",
    })

    tasks.append({
        "id": "bench_str_10_multiply_strings",
        "category": "code",
        "domain": "strings_two_pointers",
        "prompt": "Implement multiply_strings(num1: str, num2: str) -> str multiplying two non-negative integers represented as strings.",
        "reference_solution": (
            "def multiply_strings(num1: str, num2: str) -> str:\n"
            "    if num1 == '0' or num2 == '0': return '0'\n"
            "    m, n = len(num1), len(num2)\n"
            "    res = [0] * (m + n)\n"
            "    for i in range(m - 1, -1, -1):\n"
            "        for j in range(n - 1, -1, -1):\n"
            "            mul = (ord(num1[i]) - 48) * (ord(num2[j]) - 48)\n"
            "            p1, p2 = i + j, i + j + 1\n"
            "            s = mul + res[p2]\n"
            "            res[p2] = s % 10\n"
            "            res[p1] += s // 10\n"
            "    s = ''.join(str(d) for d in res).lstrip('0')\n"
            "    return s if s else '0'\n"
        ),
        "hidden_tests": "assert multiply_strings('2', '3') == '6'\nassert multiply_strings('123', '456') == '56088'",
    })

    tasks.append({
        "id": "bench_str_11_strstr_needle",
        "category": "code",
        "domain": "strings_two_pointers",
        "prompt": "Implement find_needle(haystack: str, needle: str) -> int returning index of first occurrence of needle in haystack or -1.",
        "reference_solution": (
            "def find_needle(haystack: str, needle: str) -> int:\n"
            "    if not needle: return 0\n"
            "    return haystack.find(needle)\n"
        ),
        "hidden_tests": "assert find_needle('sadbutsad', 'sad') == 0\nassert find_needle('leetcode', 'leeto') == -1",
    })

    tasks.append({
        "id": "bench_str_12_roman_to_int",
        "category": "code",
        "domain": "strings_two_pointers",
        "prompt": "Implement roman_to_int(s: str) -> int converting Roman numeral to integer.",
        "reference_solution": (
            "def roman_to_int(s: str) -> int:\n"
            "    vals = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}\n"
            "    total = 0\n"
            "    for i in range(len(s)):\n"
            "        if i + 1 < len(s) and vals[s[i]] < vals[s[i + 1]]:\n"
            "            total -= vals[s[i]]\n"
            "        else:\n"
            "            total += vals[s[i]]\n"
            "    return total\n"
        ),
        "hidden_tests": "assert roman_to_int('III') == 3\nassert roman_to_int('LVIII') == 58\nassert roman_to_int('MCMXCIV') == 1994",
    })

    tasks.append({
        "id": "bench_str_13_int_to_roman",
        "category": "code",
        "domain": "strings_two_pointers",
        "prompt": "Implement int_to_roman(num: int) -> str converting integer to Roman numeral.",
        "reference_solution": (
            "def int_to_roman(num: int) -> str:\n"
            "    mapping = [(1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'), (100, 'C'), (90, 'XC'), (50, 'L'), (40, 'XL'), (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I')]\n"
            "    res = []\n"
            "    for v, sym in mapping:\n"
            "        if num == 0: break\n"
            "        count, num = divmod(num, v)\n"
            "        res.append(sym * count)\n"
            "    return ''.join(res)\n"
        ),
        "hidden_tests": "assert int_to_roman(3749) == 'MMMDCCXLIX'\nassert int_to_roman(58) == 'LVIII'\nassert int_to_roman(1994) == 'MCMXCIV'",
    })

    tasks.append({
        "id": "bench_str_14_count_and_say",
        "category": "code",
        "domain": "strings_two_pointers",
        "prompt": "Implement count_and_say(n: int) -> str generating the nth term of the count-and-say sequence.",
        "reference_solution": (
            "def count_and_say(n: int) -> str:\n"
            "    s = '1'\n"
            "    for _ in range(n - 1):\n"
            "        nxt = []\n"
            "        i = 0\n"
            "        while i < len(s):\n"
            "            c = s[i]\n"
            "            count = 0\n"
            "            while i < len(s) and s[i] == c: count += 1; i += 1\n"
            "            nxt.append(f'{count}{c}')\n"
            "        s = ''.join(nxt)\n"
            "    return s\n"
        ),
        "hidden_tests": "assert count_and_say(1) == '1'\nassert count_and_say(4) == '1211'",
    })

    tasks.append({
        "id": "bench_str_15_length_of_last_word",
        "category": "code",
        "domain": "strings_two_pointers",
        "prompt": "Implement length_of_last_word(s: str) -> int returning length of last word in string.",
        "reference_solution": (
            "def length_of_last_word(s: str) -> int:\n"
            "    words = s.strip().split()\n"
            "    return len(words[-1]) if words else 0\n"
        ),
        "hidden_tests": "assert length_of_last_word('Hello World') == 5\nassert length_of_last_word('   fly me   to   the moon  ') == 4",
    })

    tasks.append({
        "id": "bench_str_16_add_binary",
        "category": "code",
        "domain": "strings_two_pointers",
        "prompt": "Implement add_binary(a: str, b: str) -> str adding two binary strings returning binary sum.",
        "reference_solution": (
            "def add_binary(a: str, b: str) -> str:\n"
            "    return bin(int(a, 2) + int(b, 2))[2:]\n"
        ),
        "hidden_tests": "assert add_binary('11', '1') == '100'\nassert add_binary('1010', '1011') == '10101'",
    })

    tasks.append({
        "id": "bench_str_17_simplify_path",
        "category": "code",
        "domain": "strings_two_pointers",
        "prompt": "Implement simplify_path(path: str) -> str converting Unix style absolute path into canonical path.",
        "reference_solution": (
            "def simplify_path(path: str) -> str:\n"
            "    stack = []\n"
            "    for part in path.split('/'):\n"
            "        if part in ('', '.'): continue\n"
            "        elif part == '..':\n"
            "            if stack: stack.pop()\n"
            "        else:\n"
            "            stack.append(part)\n"
            "    return '/' + '/'.join(stack)\n"
        ),
        "hidden_tests": "assert simplify_path('/home/') == '/home'\nassert simplify_path('/home//foo/') == '/home/foo'\nassert simplify_path('/home/user/Documents/../Pictures') == '/home/user/Pictures'",
    })

    tasks.append({
        "id": "bench_str_18_word_pattern",
        "category": "code",
        "domain": "strings_two_pointers",
        "prompt": "Implement word_pattern(pattern: str, s: str) -> bool returning True if s follows the exact bijection pattern.",
        "reference_solution": (
            "def word_pattern(pattern: str, s: str) -> bool:\n"
            "    words = s.split()\n"
            "    if len(pattern) != len(words): return False\n"
            "    return len(set(zip(pattern, words))) == len(set(pattern)) == len(set(words))\n"
        ),
        "hidden_tests": "assert word_pattern('abba', 'dog cat cat dog') == True\nassert word_pattern('abba', 'dog cat cat fish') == False\nassert word_pattern('aaaa', 'dog cat cat dog') == False",
    })

    tasks.append({
        "id": "bench_str_19_isomorphic_strings",
        "category": "code",
        "domain": "strings_two_pointers",
        "prompt": "Implement is_isomorphic(s: str, t: str) -> bool determining if two strings s and t are isomorphic.",
        "reference_solution": (
            "def is_isomorphic(s: str, t: str) -> bool:\n"
            "    if len(s) != len(t): return False\n"
            "    return len(set(zip(s, t))) == len(set(s)) == len(set(t))\n"
        ),
        "hidden_tests": "assert is_isomorphic('egg', 'add') == True\nassert is_isomorphic('foo', 'bar') == False\nassert is_isomorphic('paper', 'title') == True",
    })

    tasks.append({
        "id": "bench_str_20_decode_string",
        "category": "code",
        "domain": "strings_two_pointers",
        "prompt": "Implement decode_string(s: str) -> str decoding encoded string like '3[a]2[bc]' into 'aaabcbc'.",
        "reference_solution": (
            "def decode_string(s: str) -> str:\n"
            "    stack = []\n"
            "    curr_str = ''\n"
            "    curr_num = 0\n"
            "    for c in s:\n"
            "        if c.isdigit(): curr_num = curr_num * 10 + int(c)\n"
            "        elif c == '[':\n"
            "            stack.append((curr_str, curr_num))\n"
            "            curr_str = ''; curr_num = 0\n"
            "        elif c == ']':\n"
            "            prev_str, num = stack.pop()\n"
            "            curr_str = prev_str + curr_str * num\n"
            "        else:\n"
            "            curr_str += c\n"
            "    return curr_str\n"
        ),
        "hidden_tests": "assert decode_string('3[a]2[bc]') == 'aaabcbc'\nassert decode_string('3[a2[c]]') == 'accaccacc'\nassert decode_string('2[abc]3[cd]ef') == 'abcabccdcdcdef'",
    })

    # =========================================================================
    # 3. STACK & QUEUE (20 problems)
    # =========================================================================
    tasks.append({
        "id": "bench_stack_01_valid_parentheses",
        "category": "code",
        "domain": "stack_queue",
        "prompt": "Implement is_valid_parentheses(s: str) -> bool validating parentheses '()[]{}'.",
        "reference_solution": (
            "def is_valid_parentheses(s: str) -> bool:\n"
            "    mapping = {')': '(', ']': '[', '}': '{'}\n"
            "    stack = []\n"
            "    for c in s:\n"
            "        if c in mapping:\n"
            "            top = stack.pop() if stack else '#'\n"
            "            if mapping[c] != top: return False\n"
            "        else:\n"
            "            stack.append(c)\n"
            "    return not stack\n"
        ),
        "hidden_tests": "assert is_valid_parentheses('()[]{}') == True\nassert is_valid_parentheses('(]') == False\nassert is_valid_parentheses('([])') == True",
    })

    tasks.append({
        "id": "bench_stack_02_eval_rpn",
        "category": "code",
        "domain": "stack_queue",
        "prompt": "Implement eval_rpn(tokens: list) -> int evaluating Reverse Polish Notation expression.",
        "reference_solution": (
            "def eval_rpn(tokens: list) -> int:\n"
            "    stack = []\n"
            "    for t in tokens:\n"
            "        if t in {'+', '-', '*', '/'}:\n"
            "            b, a = stack.pop(), stack.pop()\n"
            "            if t == '+': stack.append(a + b)\n"
            "            elif t == '-': stack.append(a - b)\n"
            "            elif t == '*': stack.append(a * b)\n"
            "            else: stack.append(int(float(a) / b))\n"
            "        else:\n"
            "            stack.append(int(t))\n"
            "    return stack[0]\n"
        ),
        "hidden_tests": "assert eval_rpn(['2', '1', '+', '3', '*']) == 9\nassert eval_rpn(['4', '13', '5', '/', '+']) == 6",
    })

    tasks.append({
        "id": "bench_stack_03_daily_temperatures",
        "category": "code",
        "domain": "stack_queue",
        "prompt": "Implement daily_temperatures(temperatures: list) -> list returning number of days to wait for a warmer temperature.",
        "reference_solution": (
            "def daily_temperatures(temperatures: list) -> list:\n"
            "    res = [0] * len(temperatures)\n"
            "    stack = []\n"
            "    for i, t in enumerate(temperatures):\n"
            "        while stack and temperatures[stack[-1]] < t:\n"
            "            idx = stack.pop()\n"
            "            res[idx] = i - idx\n"
            "        stack.append(i)\n"
            "    return res\n"
        ),
        "hidden_tests": "assert daily_temperatures([73, 74, 75, 71, 69, 72, 76, 73]) == [1, 1, 4, 2, 1, 1, 0, 0]\nassert daily_temperatures([30, 40, 50, 60]) == [1, 1, 1, 0]",
    })

    tasks.append({
        "id": "bench_stack_04_min_stack",
        "category": "code",
        "domain": "stack_queue",
        "prompt": "Implement MinStack class supporting push, pop, top, and get_min in O(1) time.",
        "reference_solution": (
            "class MinStack:\n"
            "    def __init__(self):\n"
            "        self.stack = []\n"
            "        self.min_stack = []\n"
            "    def push(self, val: int) -> None:\n"
            "        self.stack.append(val)\n"
            "        if not self.min_stack or val <= self.min_stack[-1]:\n"
            "            self.min_stack.append(val)\n"
            "    def pop(self) -> None:\n"
            "        val = self.stack.pop()\n"
            "        if val == self.min_stack[-1]:\n"
            "            self.min_stack.pop()\n"
            "    def top(self) -> int:\n"
            "        return self.stack[-1]\n"
            "    def get_min(self) -> int:\n"
            "        return self.min_stack[-1]\n"
        ),
        "hidden_tests": "ms = MinStack()\nms.push(-2); ms.push(0); ms.push(-3)\nassert ms.get_min() == -3\nms.pop()\nassert ms.top() == 0\nassert ms.get_min() == -2",
    })

    tasks.append({
        "id": "bench_stack_05_next_greater_element",
        "category": "code",
        "domain": "stack_queue",
        "prompt": "Implement next_greater_element(nums1: list, nums2: list) -> list returning next greater element for each x in nums1.",
        "reference_solution": (
            "def next_greater_element(nums1: list, nums2: list) -> list:\n"
            "    mapping = {}\n"
            "    stack = []\n"
            "    for x in nums2:\n"
            "        while stack and stack[-1] < x:\n"
            "            mapping[stack.pop()] = x\n"
            "        stack.append(x)\n"
            "    return [mapping.get(x, -1) for x in nums1]\n"
        ),
        "hidden_tests": "assert next_greater_element([4, 1, 2], [1, 3, 4, 2]) == [-1, 3, -1]\nassert next_greater_element([2, 4], [1, 2, 3, 4]) == [3, -1]",
    })

    tasks.append({
        "id": "bench_stack_06_sliding_window_max",
        "category": "code",
        "domain": "stack_queue",
        "prompt": "Implement sliding_window_max(nums: list, k: int) -> list returning max in each sliding window of size k.",
        "reference_solution": (
            "def sliding_window_max(nums: list, k: int) -> list:\n"
            "    from collections import deque\n"
            "    q = deque()\n"
            "    res = []\n"
            "    for i, x in enumerate(nums):\n"
            "        if q and q[0] <= i - k: q.popleft()\n"
            "        while q and nums[q[-1]] <= x: q.pop()\n"
            "        q.append(i)\n"
            "        if i >= k - 1: res.append(nums[q[0]])\n"
            "    return res\n"
        ),
        "hidden_tests": "assert sliding_window_max([1, 3, -1, -3, 5, 3, 6, 7], 3) == [3, 3, 5, 5, 6, 7]\nassert sliding_window_max([1], 1) == [1]",
    })

    tasks.append({
        "id": "bench_stack_07_asteroid_collision",
        "category": "code",
        "domain": "stack_queue",
        "prompt": "Implement asteroid_collision(asteroids: list) -> list calculating surviving asteroids after collisions.",
        "reference_solution": (
            "def asteroid_collision(asteroids: list) -> list:\n"
            "    stack = []\n"
            "    for ast in asteroids:\n"
            "        while stack and ast < 0 < stack[-1]:\n"
            "            if stack[-1] < -ast:\n"
            "                stack.pop()\n"
            "                continue\n"
            "            elif stack[-1] == -ast:\n"
            "                stack.pop()\n"
            "            break\n"
            "        else:\n"
            "            stack.append(ast)\n"
            "    return stack\n"
        ),
        "hidden_tests": "assert asteroid_collision([5, 10, -5]) == [5, 10]\nassert asteroid_collision([8, -8]) == []\nassert asteroid_collision([10, 2, -5]) == [10]",
    })

    tasks.append({
        "id": "bench_stack_08_remove_k_digits",
        "category": "code",
        "domain": "stack_queue",
        "prompt": "Implement remove_k_digits(num: str, k: int) -> str returning smallest possible integer after removing k digits.",
        "reference_solution": (
            "def remove_k_digits(num: str, k: int) -> str:\n"
            "    stack = []\n"
            "    for d in num:\n"
            "        while k > 0 and stack and stack[-1] > d:\n"
            "            stack.pop(); k -= 1\n"
            "        stack.append(d)\n"
            "    final = stack[:-k] if k > 0 else stack\n"
            "    res = ''.join(final).lstrip('0')\n"
            "    return res if res else '0'\n"
        ),
        "hidden_tests": "assert remove_k_digits('1432219', 3) == '1219'\nassert remove_k_digits('10200', 1) == '200'\nassert remove_k_digits('10', 2) == '0'",
    })

    tasks.append({
        "id": "bench_stack_09_backspace_compare",
        "category": "code",
        "domain": "stack_queue",
        "prompt": "Implement backspace_compare(s: str, t: str) -> bool returning True if both strings are equal after backspacing '#'.",
        "reference_solution": (
            "def backspace_compare(s: str, t: str) -> bool:\n"
            "    def build(st):\n"
            "        res = []\n"
            "        for c in st:\n"
            "            if c == '#':\n"
            "                if res: res.pop()\n"
            "            else: res.append(c)\n"
            "        return ''.join(res)\n"
            "    return build(s) == build(t)\n"
        ),
        "hidden_tests": "assert backspace_compare('ab#c', 'ad#c') == True\nassert backspace_compare('ab##', 'c#d#') == True\nassert backspace_compare('a#c', 'b') == False",
    })

    tasks.append({
        "id": "bench_stack_10_validate_stack_sequences",
        "category": "code",
        "domain": "stack_queue",
        "prompt": "Implement validate_stack_sequences(pushed: list, popped: list) -> bool validating push/pop sequence feasibility.",
        "reference_solution": (
            "def validate_stack_sequences(pushed: list, popped: list) -> bool:\n"
            "    stack = []\n"
            "    j = 0\n"
            "    for x in pushed:\n"
            "        stack.append(x)\n"
            "        while stack and j < len(popped) and stack[-1] == popped[j]:\n"
            "            stack.pop(); j += 1\n"
            "    return j == len(popped)\n"
        ),
        "hidden_tests": "assert validate_stack_sequences([1, 2, 3, 4, 5], [4, 5, 3, 2, 1]) == True\nassert validate_stack_sequences([1, 2, 3, 4, 5], [4, 3, 5, 1, 2]) == False",
    })

    tasks.append({
        "id": "bench_stack_11_queue_using_stacks",
        "category": "code",
        "domain": "stack_queue",
        "prompt": "Implement MyQueue class using two stacks supporting push, pop, peek, and empty.",
        "reference_solution": (
            "class MyQueue:\n"
            "    def __init__(self):\n"
            "        self.s1 = []\n"
            "        self.s2 = []\n"
            "    def push(self, x: int) -> None: self.s1.append(x)\n"
            "    def pop(self) -> int:\n"
            "        self.peek()\n"
            "        return self.s2.pop()\n"
            "    def peek(self) -> int:\n"
            "        if not self.s2:\n"
            "            while self.s1: self.s2.append(self.s1.pop())\n"
            "        return self.s2[-1]\n"
            "    def empty(self) -> bool:\n"
            "        return not self.s1 and not self.s2\n"
        ),
        "hidden_tests": "q = MyQueue()\nq.push(1); q.push(2)\nassert q.peek() == 1\nassert q.pop() == 1\nassert q.empty() == False",
    })

    tasks.append({
        "id": "bench_stack_12_stack_using_queues",
        "category": "code",
        "domain": "stack_queue",
        "prompt": "Implement MyStack class using a queue supporting push, pop, top, and empty.",
        "reference_solution": (
            "from collections import deque\n"
            "class MyStack:\n"
            "    def __init__(self):\n"
            "        self.q = deque()\n"
            "    def push(self, x: int) -> None:\n"
            "        self.q.append(x)\n"
            "        for _ in range(len(self.q) - 1):\n"
            "            self.q.append(self.q.popleft())\n"
            "    def pop(self) -> int: return self.q.popleft()\n"
            "    def top(self) -> int: return self.q[0]\n"
            "    def empty(self) -> bool: return len(self.q) == 0\n"
        ),
        "hidden_tests": "st = MyStack()\nst.push(1); st.push(2)\nassert st.top() == 2\nassert st.pop() == 2\nassert st.empty() == False",
    })

    tasks.append({
        "id": "bench_stack_13_basic_calculator",
        "category": "code",
        "domain": "stack_queue",
        "prompt": "Implement calculate_basic(s: str) -> int evaluating expressions with '+', '-', '(', ')'.",
        "reference_solution": (
            "def calculate_basic(s: str) -> int:\n"
            "    stack = []\n"
            "    res = 0; num = 0; sign = 1\n"
            "    for c in s:\n"
            "        if c.isdigit(): num = num * 10 + int(c)\n"
            "        elif c in '+-':\n"
            "            res += sign * num\n"
            "            num = 0\n"
            "            sign = 1 if c == '+' else -1\n"
            "        elif c == '(':\n"
            "            stack.append((res, sign))\n"
            "            res = 0; sign = 1\n"
            "        elif c == ')':\n"
            "            res += sign * num\n"
            "            num = 0\n"
            "            prev_res, prev_sign = stack.pop()\n"
            "            res = prev_res + prev_sign * res\n"
            "    return res + sign * num\n"
        ),
        "hidden_tests": "assert calculate_basic('1 + 1') == 2\nassert calculate_basic(' 2-1 + 2 ') == 3\nassert calculate_basic('(1+(4+5+2)-3)+(6+8)') == 23",
    })

    tasks.append({
        "id": "bench_stack_14_score_of_parentheses",
        "category": "code",
        "domain": "stack_queue",
        "prompt": "Implement score_of_parentheses(s: str) -> int where () has score 1, AB is A+B, and (A) is 2*A.",
        "reference_solution": (
            "def score_of_parentheses(s: str) -> int:\n"
            "    stack = [0]\n"
            "    for c in s:\n"
            "        if c == '(': stack.append(0)\n"
            "        else:\n"
            "            v = stack.pop()\n"
            "            stack[-1] += max(2 * v, 1)\n"
            "    return stack[0]\n"
        ),
        "hidden_tests": "assert score_of_parentheses('()') == 1\nassert score_of_parentheses('(())') == 2\nassert score_of_parentheses('()()') == 2",
    })

    tasks.append({
        "id": "bench_stack_15_make_string_great",
        "category": "code",
        "domain": "stack_queue",
        "prompt": "Implement make_good(s: str) -> str removing adjacent adjacent matching letters with opposite casing.",
        "reference_solution": (
            "def make_good(s: str) -> str:\n"
            "    stack = []\n"
            "    for c in s:\n"
            "        if stack and abs(ord(stack[-1]) - ord(c)) == 32:\n"
            "            stack.pop()\n"
            "        else:\n"
            "            stack.append(c)\n"
            "    return ''.join(stack)\n"
        ),
        "hidden_tests": "assert make_good('leEeetcode') == 'leetcode'\nassert make_good('abBAcC') == ''\nassert make_good('s') == 's'",
    })

    tasks.append({
        "id": "bench_stack_16_baseball_game",
        "category": "code",
        "domain": "stack_queue",
        "prompt": "Implement cal_points(operations: list) -> int computing total score with integers, '+', 'D', 'C'.",
        "reference_solution": (
            "def cal_points(operations: list) -> int:\n"
            "    record = []\n"
            "    for op in operations:\n"
            "        if op == '+': record.append(record[-1] + record[-2])\n"
            "        elif op == 'D': record.append(2 * record[-1])\n"
            "        elif op == 'C': record.pop()\n"
            "        else: record.append(int(op))\n"
            "    return sum(record)\n"
        ),
        "hidden_tests": "assert cal_points(['5', '2', 'C', 'D', '+']) == 30\nassert cal_points(['5', '-2', '4', 'C', 'D', '9', '+', '+']) == 27",
    })

    tasks.append({
        "id": "bench_stack_17_remove_adjacent_duplicates",
        "category": "code",
        "domain": "stack_queue",
        "prompt": "Implement remove_adjacent_duplicates(s: str) -> str removing all adjacent duplicate characters.",
        "reference_solution": (
            "def remove_adjacent_duplicates(s: str) -> str:\n"
            "    stack = []\n"
            "    for c in s:\n"
            "        if stack and stack[-1] == c: stack.pop()\n"
            "        else: stack.append(c)\n"
            "    return ''.join(stack)\n"
        ),
        "hidden_tests": "assert remove_adjacent_duplicates('abbaca') == 'ca'\nassert remove_adjacent_duplicates('azxxzy') == 'ay'",
    })

    tasks.append({
        "id": "bench_stack_18_crawler_log_folder",
        "category": "code",
        "domain": "stack_queue",
        "prompt": "Implement min_operations_folder(logs: list) -> int returning min operations to return to main folder.",
        "reference_solution": (
            "def min_operations_folder(logs: list) -> int:\n"
            "    depth = 0\n"
            "    for log in logs:\n"
            "        if log == '../': depth = max(0, depth - 1)\n"
            "        elif log == './': pass\n"
            "        else: depth += 1\n"
            "    return depth\n"
        ),
        "hidden_tests": "assert min_operations_folder(['d1/', 'd2/', '../', 'd21/', './']) == 2\nassert min_operations_folder(['d1/', '../', '../', '../']) == 0",
    })

    tasks.append({
        "id": "bench_stack_19_final_prices_discount",
        "category": "code",
        "domain": "stack_queue",
        "prompt": "Implement final_prices(prices: list) -> list applying discount of next lower or equal price.",
        "reference_solution": (
            "def final_prices(prices: list) -> list:\n"
            "    res = list(prices)\n"
            "    stack = []\n"
            "    for i, p in enumerate(prices):\n"
            "        while stack and prices[stack[-1]] >= p:\n"
            "            res[stack.pop()] -= p\n"
            "        stack.append(i)\n"
            "    return res\n"
        ),
        "hidden_tests": "assert final_prices([8, 4, 6, 2, 3]) == [4, 2, 4, 2, 3]\nassert final_prices([1, 2, 3, 4, 5]) == [1, 2, 3, 4, 5]",
    })

    tasks.append({
        "id": "bench_stack_20_exclusive_time_functions",
        "category": "code",
        "domain": "stack_queue",
        "prompt": "Implement exclusive_time(n: int, logs: list) -> list calculating total execution time for each function.",
        "reference_solution": (
            "def exclusive_time(n: int, logs: list) -> list:\n"
            "    res = [0] * n\n"
            "    stack = []\n"
            "    prev_time = 0\n"
            "    for log in logs:\n"
            "        fid, typ, t = log.split(':')\n"
            "        fid, t = int(fid), int(t)\n"
            "        if typ == 'start':\n"
            "            if stack: res[stack[-1]] += t - prev_time\n"
            "            stack.append(fid)\n"
            "            prev_time = t\n"
            "        else:\n"
            "            res[stack.pop()] += t - prev_time + 1\n"
            "            prev_time = t + 1\n"
            "    return res\n"
        ),
        "hidden_tests": "assert exclusive_time(2, ['0:start:0', '1:start:2', '1:end:5', '0:end:6']) == [3, 4]\nassert exclusive_time(1, ['0:start:0', '0:end:0']) == [1]",
    })

    # =========================================================================
    # 4. TREES, GRAPHS & RECURSION (20 problems)
    # =========================================================================
    tasks.append({
        "id": "bench_tree_01_max_depth_binary_tree",
        "category": "code",
        "domain": "trees_graphs_recursion",
        "prompt": "Implement max_depth(root: dict) -> int returning max depth of binary tree represented as nested dict {'val': x, 'left': ..., 'right': ...}.",
        "reference_solution": (
            "def max_depth(root: dict) -> int:\n"
            "    if not root: return 0\n"
            "    return 1 + max(max_depth(root.get('left')), max_depth(root.get('right')))\n"
        ),
        "hidden_tests": "t = {'val': 3, 'left': {'val': 9}, 'right': {'val': 20, 'left': {'val': 15}, 'right': {'val': 7}}}\nassert max_depth(t) == 3\nassert max_depth(None) == 0",
    })

    tasks.append({
        "id": "bench_tree_02_invert_binary_tree",
        "category": "code",
        "domain": "trees_graphs_recursion",
        "prompt": "Implement invert_tree(root: dict) -> dict inverting a binary tree.",
        "reference_solution": (
            "def invert_tree(root: dict) -> dict:\n"
            "    if not root: return None\n"
            "    return {\n"
            "        'val': root['val'],\n"
            "        'left': invert_tree(root.get('right')),\n"
            "        'right': invert_tree(root.get('left')),\n"
            "    }\n"
        ),
        "hidden_tests": "t = {'val': 4, 'left': {'val': 2}, 'right': {'val': 7}}\ninv = invert_tree(t)\nassert inv['left']['val'] == 7 and inv['right']['val'] == 2",
    })

    tasks.append({
        "id": "bench_tree_03_same_tree",
        "category": "code",
        "domain": "trees_graphs_recursion",
        "prompt": "Implement is_same_tree(p: dict, q: dict) -> bool returning True if both binary trees are structurally identical with same values.",
        "reference_solution": (
            "def is_same_tree(p: dict, q: dict) -> bool:\n"
            "    if not p and not q: return True\n"
            "    if not p or not q or p.get('val') != q.get('val'): return False\n"
            "    return is_same_tree(p.get('left'), q.get('left')) and is_same_tree(p.get('right'), q.get('right'))\n"
        ),
        "hidden_tests": "t1 = {'val': 1, 'left': {'val': 2}}\nt2 = {'val': 1, 'left': {'val': 2}}\nassert is_same_tree(t1, t2) == True\nassert is_same_tree(t1, None) == False",
    })

    tasks.append({
        "id": "bench_tree_04_symmetric_tree",
        "category": "code",
        "domain": "trees_graphs_recursion",
        "prompt": "Implement is_symmetric(root: dict) -> bool checking if a binary tree is a mirror of itself.",
        "reference_solution": (
            "def is_symmetric(root: dict) -> bool:\n"
            "    if not root: return True\n"
            "    def is_mirror(t1, t2):\n"
            "        if not t1 and not t2: return True\n"
            "        if not t1 or not t2 or t1.get('val') != t2.get('val'): return False\n"
            "        return is_mirror(t1.get('left'), t2.get('right')) and is_mirror(t1.get('right'), t2.get('left'))\n"
            "    return is_mirror(root.get('left'), root.get('right'))\n"
        ),
        "hidden_tests": "sym = {'val': 1, 'left': {'val': 2, 'right': {'val': 3}}, 'right': {'val': 2, 'left': {'val': 3}}}\nassert is_symmetric(sym) == True\nasym = {'val': 1, 'left': {'val': 2}, 'right': {'val': 3}}\nassert is_symmetric(asym) == False",
    })

    tasks.append({
        "id": "bench_tree_05_path_sum",
        "category": "code",
        "domain": "trees_graphs_recursion",
        "prompt": "Implement has_path_sum(root: dict, target_sum: int) -> bool checking if tree has root-to-leaf path summing to target_sum.",
        "reference_solution": (
            "def has_path_sum(root: dict, target_sum: int) -> bool:\n"
            "    if not root: return False\n"
            "    rem = target_sum - root['val']\n"
            "    if not root.get('left') and not root.get('right'):\n"
            "        return rem == 0\n"
            "    return has_path_sum(root.get('left'), rem) or has_path_sum(root.get('right'), rem)\n"
        ),
        "hidden_tests": "t = {'val': 5, 'left': {'val': 4, 'left': {'val': 11}}, 'right': {'val': 8}}\nassert has_path_sum(t, 20) == True\nassert has_path_sum(t, 99) == False",
    })

    tasks.append({
        "id": "bench_tree_06_tree_diameter",
        "category": "code",
        "domain": "trees_graphs_recursion",
        "prompt": "Implement tree_diameter(root: dict) -> int returning length of longest path between any two nodes in tree.",
        "reference_solution": (
            "def tree_diameter(root: dict) -> int:\n"
            "    diameter = 0\n"
            "    def depth(node):\n"
            "        nonlocal diameter\n"
            "        if not node: return 0\n"
            "        l, r = depth(node.get('left')), depth(node.get('right'))\n"
            "        diameter = max(diameter, l + r)\n"
            "        return 1 + max(l, r)\n"
            "    depth(root)\n"
            "    return diameter\n"
        ),
        "hidden_tests": "t = {'val': 1, 'left': {'val': 2, 'left': {'val': 4}, 'right': {'val': 5}}, 'right': {'val': 3}}\nassert tree_diameter(t) == 3",
    })

    tasks.append({
        "id": "bench_tree_07_level_order_traversal",
        "category": "code",
        "domain": "trees_graphs_recursion",
        "prompt": "Implement level_order(root: dict) -> list returning level order traversal of binary tree node values.",
        "reference_solution": (
            "def level_order(root: dict) -> list:\n"
            "    if not root: return []\n"
            "    from collections import deque\n"
            "    q = deque([root])\n"
            "    res = []\n"
            "    while q:\n"
            "        level = []\n"
            "        for _ in range(len(q)):\n"
            "            n = q.popleft()\n"
            "            level.append(n['val'])\n"
            "            if n.get('left'): q.append(n['left'])\n"
            "            if n.get('right'): q.append(n['right'])\n"
            "        res.append(level)\n"
            "    return res\n"
        ),
        "hidden_tests": "t = {'val': 3, 'left': {'val': 9}, 'right': {'val': 20, 'left': {'val': 15}, 'right': {'val': 7}}}\nassert level_order(t) == [[3], [9, 20], [15, 7]]",
    })

    tasks.append({
        "id": "bench_tree_08_validate_bst",
        "category": "code",
        "domain": "trees_graphs_recursion",
        "prompt": "Implement is_valid_bst(root: dict) -> bool validating if binary tree is a valid Binary Search Tree.",
        "reference_solution": (
            "def is_valid_bst(root: dict) -> bool:\n"
            "    def check(node, low=float('-inf'), high=float('inf')):\n"
            "        if not node: return True\n"
            "        val = node['val']\n"
            "        if not (low < val < high): return False\n"
            "        return check(node.get('left'), low, val) and check(node.get('right'), val, high)\n"
            "    return check(root)\n"
        ),
        "hidden_tests": "valid_bst = {'val': 2, 'left': {'val': 1}, 'right': {'val': 3}}\nassert is_valid_bst(valid_bst) == True\ninvalid_bst = {'val': 5, 'left': {'val': 1}, 'right': {'val': 4, 'left': {'val': 3}, 'right': {'val': 6}}}\nassert is_valid_bst(invalid_bst) == False",
    })

    tasks.append({
        "id": "bench_tree_09_lowest_common_ancestor_bst",
        "category": "code",
        "domain": "trees_graphs_recursion",
        "prompt": "Implement lca_bst(root: dict, p: int, q: int) -> int returning value of Lowest Common Ancestor of p and q in BST.",
        "reference_solution": (
            "def lca_bst(root: dict, p: int, q: int) -> int:\n"
            "    curr = root\n"
            "    while curr:\n"
            "        if p < curr['val'] and q < curr['val']: curr = curr.get('left')\n"
            "        elif p > curr['val'] and q > curr['val']: curr = curr.get('right')\n"
            "        else: return curr['val']\n"
            "    return -1\n"
        ),
        "hidden_tests": "bst = {'val': 6, 'left': {'val': 2, 'left': {'val': 0}, 'right': {'val': 4}}, 'right': {'val': 8}}\nassert lca_bst(bst, 2, 8) == 6\nassert lca_bst(bst, 2, 4) == 2",
    })

    tasks.append({
        "id": "bench_tree_10_count_good_nodes",
        "category": "code",
        "domain": "trees_graphs_recursion",
        "prompt": "Implement good_nodes(root: dict) -> int counting nodes with value >= maximum value from root to that node.",
        "reference_solution": (
            "def good_nodes(root: dict) -> int:\n"
            "    def dfs(node, max_val):\n"
            "        if not node: return 0\n"
            "        is_good = 1 if node['val'] >= max_val else 0\n"
            "        new_max = max(max_val, node['val'])\n"
            "        return is_good + dfs(node.get('left'), new_max) + dfs(node.get('right'), new_max)\n"
            "    return dfs(root, float('-inf'))\n"
        ),
        "hidden_tests": "t = {'val': 3, 'left': {'val': 1, 'left': {'val': 3}}, 'right': {'val': 4, 'left': {'val': 1}, 'right': {'val': 5}}}\nassert good_nodes(t) == 4",
    })

    tasks.append({
        "id": "bench_tree_11_right_side_view",
        "category": "code",
        "domain": "trees_graphs_recursion",
        "prompt": "Implement right_side_view(root: dict) -> list returning values of nodes visible from right side of tree.",
        "reference_solution": (
            "def right_side_view(root: dict) -> list:\n"
            "    if not root: return []\n"
            "    from collections import deque\n"
            "    q = deque([root])\n"
            "    res = []\n"
            "    while q:\n"
            "        size = len(q)\n"
            "        for i in range(size):\n"
            "            n = q.popleft()\n"
            "            if i == size - 1: res.append(n['val'])\n"
            "            if n.get('left'): q.append(n['left'])\n"
            "            if n.get('right'): q.append(n['right'])\n"
            "    return res\n"
        ),
        "hidden_tests": "t = {'val': 1, 'left': {'val': 2, 'right': {'val': 5}}, 'right': {'val': 3, 'right': {'val': 4}}}\nassert right_side_view(t) == [1, 3, 4]",
    })

    tasks.append({
        "id": "bench_tree_12_flatten_binary_tree",
        "category": "code",
        "domain": "trees_graphs_recursion",
        "prompt": "Implement flatten_tree(root: dict) -> list returning preorder traversal values of flattened binary tree.",
        "reference_solution": (
            "def flatten_tree(root: dict) -> list:\n"
            "    res = []\n"
            "    def preorder(node):\n"
            "        if not node: return\n"
            "        res.append(node['val'])\n"
            "        preorder(node.get('left'))\n"
            "        preorder(node.get('right'))\n"
            "    preorder(root)\n"
            "    return res\n"
        ),
        "hidden_tests": "t = {'val': 1, 'left': {'val': 2, 'left': {'val': 3}, 'right': {'val': 4}}, 'right': {'val': 5}}\nassert flatten_tree(t) == [1, 2, 3, 4, 5]",
    })

    tasks.append({
        "id": "bench_tree_13_graph_bfs",
        "category": "code",
        "domain": "trees_graphs_recursion",
        "prompt": "Implement bfs_traversal(graph: dict, start: int) -> list returning BFS traversal order starting at node.",
        "reference_solution": (
            "def bfs_traversal(graph: dict, start: int) -> list:\n"
            "    from collections import deque\n"
            "    visited = set([start])\n"
            "    q = deque([start])\n"
            "    res = []\n"
            "    while q:\n"
            "        node = q.popleft()\n"
            "        res.append(node)\n"
            "        for neighbor in sorted(graph.get(node, [])):\n"
            "            if neighbor not in visited:\n"
            "                visited.add(neighbor)\n"
            "                q.append(neighbor)\n"
            "    return res\n"
        ),
        "hidden_tests": "g = {1: [2, 3], 2: [4], 3: [5], 4: [], 5: []}\nassert bfs_traversal(g, 1) == [1, 2, 3, 4, 5]",
    })

    tasks.append({
        "id": "bench_tree_14_graph_dfs",
        "category": "code",
        "domain": "trees_graphs_recursion",
        "prompt": "Implement dfs_traversal(graph: dict, start: int) -> list returning DFS traversal order starting at node.",
        "reference_solution": (
            "def dfs_traversal(graph: dict, start: int) -> list:\n"
            "    res = []\n"
            "    visited = set()\n"
            "    def dfs(u):\n"
            "        visited.add(u)\n"
            "        res.append(u)\n"
            "        for v in sorted(graph.get(u, [])):\n"
            "            if v not in visited: dfs(v)\n"
            "    dfs(start)\n"
            "    return res\n"
        ),
        "hidden_tests": "g = {1: [2, 3], 2: [4], 3: [5], 4: [], 5: []}\nassert dfs_traversal(g, 1) == [1, 2, 4, 3, 5]",
    })

    tasks.append({
        "id": "bench_tree_15_cycle_detection_directed",
        "category": "code",
        "domain": "trees_graphs_recursion",
        "prompt": "Implement has_cycle(num_nodes: int, edges: list) -> bool detecting cycle in directed graph.",
        "reference_solution": (
            "def has_cycle(num_nodes: int, edges: list) -> bool:\n"
            "    from collections import defaultdict\n"
            "    adj = defaultdict(list)\n"
            "    for u, v in edges: adj[u].append(v)\n"
            "    state = [0] * num_nodes  # 0=unvisited, 1=visiting, 2=visited\n"
            "    def dfs(u):\n"
            "        state[u] = 1\n"
            "        for v in adj[u]:\n"
            "            if state[v] == 1: return True\n"
            "            if state[v] == 0 and dfs(v): return True\n"
            "        state[u] = 2\n"
            "        return False\n"
            "    return any(state[i] == 0 and dfs(i) for i in range(num_nodes))\n"
        ),
        "hidden_tests": "assert has_cycle(3, [[0, 1], [1, 2], [2, 0]]) == True\nassert has_cycle(3, [[0, 1], [1, 2]]) == False",
    })

    tasks.append({
        "id": "bench_tree_16_topological_sort",
        "category": "code",
        "domain": "trees_graphs_recursion",
        "prompt": "Implement topological_sort(num_nodes: int, edges: list) -> list returning valid topological ordering or empty list if cyclic.",
        "reference_solution": (
            "def topological_sort(num_nodes: int, edges: list) -> list:\n"
            "    from collections import defaultdict, deque\n"
            "    adj = defaultdict(list)\n"
            "    indegree = [0] * num_nodes\n"
            "    for u, v in edges:\n"
            "        adj[u].append(v)\n"
            "        indegree[v] += 1\n"
            "    q = deque([i for i in range(num_nodes) if indegree[i] == 0])\n"
            "    order = []\n"
            "    while q:\n"
            "        u = q.popleft()\n"
            "        order.append(u)\n"
            "        for v in adj[u]:\n"
            "            indegree[v] -= 1\n"
            "            if indegree[v] == 0: q.append(v)\n"
            "    return order if len(order) == num_nodes else []\n"
        ),
        "hidden_tests": "assert topological_sort(4, [[1, 0], [2, 0], [3, 1], [3, 2]]) in ([3, 1, 2, 0], [3, 2, 1, 0])\nassert topological_sort(2, [[0, 1], [1, 0]]) == []",
    })

    tasks.append({
        "id": "bench_tree_17_number_of_islands",
        "category": "code",
        "domain": "trees_graphs_recursion",
        "prompt": "Implement num_islands(grid: list) -> int counting number of connected 1s islands.",
        "reference_solution": (
            "def num_islands(grid: list) -> int:\n"
            "    if not grid: return 0\n"
            "    m, n = len(grid), len(grid[0])\n"
            "    g = [list(row) for row in grid]\n"
            "    def dfs(r, c):\n"
            "        if r < 0 or r >= m or c < 0 or c >= n or g[r][c] != '1': return\n"
            "        g[r][c] = '0'\n"
            "        dfs(r+1, c); dfs(r-1, c); dfs(r, c+1); dfs(r, c-1)\n"
            "    count = 0\n"
            "    for r in range(m):\n"
            "        for c in range(n):\n"
            "            if g[r][c] == '1':\n"
            "                count += 1\n"
            "                dfs(r, c)\n"
            "    return count\n"
        ),
        "hidden_tests": "g = [['1', '1', '0', '0'], ['1', '1', '0', '0'], ['0', '0', '1', '0'], ['0', '0', '0', '1']]\nassert num_islands(g) == 3",
    })

    tasks.append({
        "id": "bench_tree_18_flood_fill",
        "category": "code",
        "domain": "trees_graphs_recursion",
        "prompt": "Implement flood_fill(image: list, sr: int, sc: int, color: int) -> list performing flood fill on image.",
        "reference_solution": (
            "def flood_fill(image: list, sr: int, sc: int, color: int) -> list:\n"
            "    orig = image[sr][sc]\n"
            "    if orig == color: return image\n"
            "    m, n = len(image), len(image[0])\n"
            "    img = [list(row) for row in image]\n"
            "    def dfs(r, c):\n"
            "        if r < 0 or r >= m or c < 0 or c >= n or img[r][c] != orig: return\n"
            "        img[r][c] = color\n"
            "        dfs(r+1, c); dfs(r-1, c); dfs(r, c+1); dfs(r, c-1)\n"
            "    dfs(sr, sc)\n"
            "    return img\n"
        ),
        "hidden_tests": "assert flood_fill([[1, 1, 1], [1, 1, 0], [1, 0, 1]], 1, 1, 2) == [[2, 2, 2], [2, 2, 0], [2, 0, 1]]",
    })

    tasks.append({
        "id": "bench_tree_19_clone_adjacency",
        "category": "code",
        "domain": "trees_graphs_recursion",
        "prompt": "Implement clone_adjacency(adj: dict) -> dict creating a deep clone of graph adjacency list with new node sets.",
        "reference_solution": (
            "def clone_adjacency(adj: dict) -> dict:\n"
            "    return {k: list(v) for k, v in adj.items()}\n"
        ),
        "hidden_tests": "orig = {1: [2, 3], 2: [1]}\ncloned = clone_adjacency(orig)\nassert cloned == orig and cloned is not orig and cloned[1] is not orig[1]",
    })

    tasks.append({
        "id": "bench_tree_20_shortest_path_unweighted",
        "category": "code",
        "domain": "trees_graphs_recursion",
        "prompt": "Implement shortest_path_bfs(graph: dict, start: int, target: int) -> int returning distance of shortest path between nodes or -1.",
        "reference_solution": (
            "def shortest_path_bfs(graph: dict, start: int, target: int) -> int:\n"
            "    if start == target: return 0\n"
            "    from collections import deque\n"
            "    visited = {start}\n"
            "    q = deque([(start, 0)])\n"
            "    while q:\n"
            "        u, dist = q.popleft()\n"
            "        if u == target: return dist\n"
            "        for v in graph.get(u, []):\n"
            "            if v not in visited:\n"
            "                visited.add(v)\n"
            "                q.append((v, dist + 1))\n"
            "    return -1\n"
        ),
        "hidden_tests": "g = {1: [2, 3], 2: [4], 3: [4], 4: [5]}\nassert shortest_path_bfs(g, 1, 5) == 3\nassert shortest_path_bfs(g, 1, 99) == -1",
    })

    # =========================================================================
    # 5. DYNAMIC PROGRAMMING (20 problems)
    # =========================================================================
    tasks.append({
        "id": "bench_dp_01_climbing_stairs",
        "category": "code",
        "domain": "dynamic_programming",
        "prompt": "Implement climb_stairs(n: int) -> int returning distinct ways to climb n stairs taking 1 or 2 steps.",
        "reference_solution": (
            "def climb_stairs(n: int) -> int:\n"
            "    if n <= 2: return n\n"
            "    a, b = 1, 2\n"
            "    for _ in range(3, n + 1): a, b = b, a + b\n"
            "    return b\n"
        ),
        "hidden_tests": "assert climb_stairs(2) == 2\nassert climb_stairs(3) == 3\nassert climb_stairs(5) == 8",
    })

    tasks.append({
        "id": "bench_dp_02_coin_change",
        "category": "code",
        "domain": "dynamic_programming",
        "prompt": "Implement coin_change(coins: list, amount: int) -> int returning minimum coins needed to make up amount or -1.",
        "reference_solution": (
            "def coin_change(coins: list, amount: int) -> int:\n"
            "    dp = [float('inf')] * (amount + 1)\n"
            "    dp[0] = 0\n"
            "    for c in coins:\n"
            "        for x in range(c, amount + 1):\n"
            "            dp[x] = min(dp[x], dp[x - c] + 1)\n"
            "    return dp[amount] if dp[amount] != float('inf') else -1\n"
        ),
        "hidden_tests": "assert coin_change([1, 2, 5], 11) == 3\nassert coin_change([2], 3) == -1\nassert coin_change([1], 0) == 0",
    })

    tasks.append({
        "id": "bench_dp_03_longest_increasing_subsequence",
        "category": "code",
        "domain": "dynamic_programming",
        "prompt": "Implement length_of_lis(nums: list) -> int returning length of longest strictly increasing subsequence.",
        "reference_solution": (
            "def length_of_lis(nums: list) -> int:\n"
            "    if not nums: return 0\n"
            "    import bisect\n"
            "    tails = []\n"
            "    for x in nums:\n"
            "        idx = bisect.bisect_left(tails, x)\n"
            "        if idx == len(tails): tails.append(x)\n"
            "        else: tails[idx] = x\n"
            "    return len(tails)\n"
        ),
        "hidden_tests": "assert length_of_lis([10, 9, 2, 5, 3, 7, 101, 18]) == 4\nassert length_of_lis([0, 1, 0, 3, 2, 3]) == 4",
    })

    tasks.append({
        "id": "bench_dp_04_house_robber",
        "category": "code",
        "domain": "dynamic_programming",
        "prompt": "Implement rob_houses(nums: list) -> int returning max money robbed without alerting adjacent houses.",
        "reference_solution": (
            "def rob_houses(nums: list) -> int:\n"
            "    rob1, rob2 = 0, 0\n"
            "    for x in nums:\n"
            "        rob1, rob2 = rob2, max(rob2, rob1 + x)\n"
            "    return rob2\n"
        ),
        "hidden_tests": "assert rob_houses([1, 2, 3, 1]) == 4\nassert rob_houses([2, 7, 9, 3, 1]) == 12",
    })

    tasks.append({
        "id": "bench_dp_05_house_robber_circular",
        "category": "code",
        "domain": "dynamic_programming",
        "prompt": "Implement rob_circular(nums: list) -> int returning max money robbed where houses are arranged in a circle.",
        "reference_solution": (
            "def rob_circular(nums: list) -> int:\n"
            "    if not nums: return 0\n"
            "    if len(nums) <= 2: return max(nums)\n"
            "    def rob_linear(arr):\n"
            "        r1, r2 = 0, 0\n"
            "        for x in arr: r1, r2 = r2, max(r2, r1 + x)\n"
            "        return r2\n"
            "    return max(rob_linear(nums[:-1]), rob_linear(nums[1:]))\n"
        ),
        "hidden_tests": "assert rob_circular([2, 3, 2]) == 3\nassert rob_circular([1, 2, 3, 1]) == 4",
    })

    tasks.append({
        "id": "bench_dp_06_unique_paths",
        "category": "code",
        "domain": "dynamic_programming",
        "prompt": "Implement unique_paths(m: int, n: int) -> int returning number of possible unique paths in m x n grid.",
        "reference_solution": (
            "def unique_paths(m: int, n: int) -> int:\n"
            "    row = [1] * n\n"
            "    for _ in range(m - 1):\n"
            "        new_row = [1] * n\n"
            "        for j in range(1, n):\n"
            "            new_row[j] = new_row[j - 1] + row[j]\n"
            "        row = new_row\n"
            "    return row[-1]\n"
        ),
        "hidden_tests": "assert unique_paths(3, 7) == 28\nassert unique_paths(3, 2) == 3",
    })

    tasks.append({
        "id": "bench_dp_07_min_path_sum",
        "category": "code",
        "domain": "dynamic_programming",
        "prompt": "Implement min_path_sum(grid: list) -> int finding a path from top left to bottom right minimizing sum of numbers.",
        "reference_solution": (
            "def min_path_sum(grid: list) -> int:\n"
            "    m, n = len(grid), len(grid[0])\n"
            "    dp = [[0] * n for _ in range(m)]\n"
            "    dp[0][0] = grid[0][0]\n"
            "    for c in range(1, n): dp[0][c] = dp[0][c - 1] + grid[0][c]\n"
            "    for r in range(1, m): dp[r][0] = dp[r - 1][0] + grid[r][0]\n"
            "    for r in range(1, m):\n"
            "        for c in range(1, n):\n"
            "            dp[r][c] = min(dp[r - 1][c], dp[r][c - 1]) + grid[r][c]\n"
            "    return dp[-1][-1]\n"
        ),
        "hidden_tests": "assert min_path_sum([[1, 3, 1], [1, 5, 1], [4, 2, 1]]) == 7\nassert min_path_sum([[1, 2, 3], [4, 5, 6]]) == 12",
    })

    tasks.append({
        "id": "bench_dp_08_decode_ways",
        "category": "code",
        "domain": "dynamic_programming",
        "prompt": "Implement num_decodings(s: str) -> int decoding 'A'->1...'Z'->26 returning number of valid decodings.",
        "reference_solution": (
            "def num_decodings(s: str) -> int:\n"
            "    if not s or s[0] == '0': return 0\n"
            "    dp = [0] * (len(s) + 1)\n"
            "    dp[0] = 1; dp[1] = 1\n"
            "    for i in range(2, len(s) + 1):\n"
            "        one = int(s[i - 1:i])\n"
            "        two = int(s[i - 2:i])\n"
            "        if 1 <= one <= 9: dp[i] += dp[i - 1]\n"
            "        if 10 <= two <= 26: dp[i] += dp[i - 2]\n"
            "    return dp[-1]\n"
        ),
        "hidden_tests": "assert num_decodings('12') == 2\nassert num_decodings('226') == 3\nassert num_decodings('06') == 0",
    })

    tasks.append({
        "id": "bench_dp_09_word_break",
        "category": "code",
        "domain": "dynamic_programming",
        "prompt": "Implement word_break(s: str, word_dict: list) -> bool checking if s can be segmented into words in word_dict.",
        "reference_solution": (
            "def word_break(s: str, word_dict: list) -> bool:\n"
            "    words = set(word_dict)\n"
            "    dp = [False] * (len(s) + 1)\n"
            "    dp[0] = True\n"
            "    for i in range(1, len(s) + 1):\n"
            "        for j in range(i):\n"
            "            if dp[j] and s[j:i] in words:\n"
            "                dp[i] = True\n"
            "                break\n"
            "    return dp[-1]\n"
        ),
        "hidden_tests": "assert word_break('leetcode', ['leet', 'code']) == True\nassert word_break('applepenapple', ['apple', 'pen']) == True\nassert word_break('catsandog', ['cats', 'dog', 'sand', 'and', 'cat']) == False",
    })

    tasks.append({
        "id": "bench_dp_10_edit_distance",
        "category": "code",
        "domain": "dynamic_programming",
        "prompt": "Implement min_distance(word1: str, word2: str) -> int returning minimum operations to convert word1 to word2.",
        "reference_solution": (
            "def min_distance(word1: str, word2: str) -> int:\n"
            "    m, n = len(word1), len(word2)\n"
            "    dp = [[0] * (n + 1) for _ in range(m + 1)]\n"
            "    for i in range(m + 1): dp[i][0] = i\n"
            "    for j in range(n + 1): dp[0][j] = j\n"
            "    for i in range(1, m + 1):\n"
            "        for j in range(1, n + 1):\n"
            "            if word1[i - 1] == word2[j - 1]: dp[i][j] = dp[i - 1][j - 1]\n"
            "            else:\n"
            "                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])\n"
            "    return dp[m][n]\n"
        ),
        "hidden_tests": "assert min_distance('horse', 'ros') == 3\nassert min_distance('intention', 'execution') == 5",
    })

    tasks.append({
        "id": "bench_dp_11_knapsack_01",
        "category": "code",
        "domain": "dynamic_programming",
        "prompt": "Implement knapsack(weights: list, values: list, capacity: int) -> int solving 0/1 knapsack problem.",
        "reference_solution": (
            "def knapsack(weights: list, values: list, capacity: int) -> int:\n"
            "    dp = [0] * (capacity + 1)\n"
            "    for w, v in zip(weights, values):\n"
            "        for cap in range(capacity, w - 1, -1):\n"
            "            dp[cap] = max(dp[cap], dp[cap - w] + v)\n"
            "    return dp[capacity]\n"
        ),
        "hidden_tests": "assert knapsack([1, 2, 3], [60, 100, 120], 5) == 220\nassert knapsack([2, 3, 4], [3, 4, 5], 5) == 7",
    })

    tasks.append({
        "id": "bench_dp_12_partition_equal_subset_sum",
        "category": "code",
        "domain": "dynamic_programming",
        "prompt": "Implement can_partition(nums: list) -> bool determining if array can be partitioned into two subsets with equal sum.",
        "reference_solution": (
            "def can_partition(nums: list) -> bool:\n"
            "    total = sum(nums)\n"
            "    if total % 2 != 0: return False\n"
            "    target = total // 2\n"
            "    dp = {0}\n"
            "    for x in nums:\n"
            "        dp = dp | {s + x for s in dp if s + x <= target}\n"
            "        if target in dp: return True\n"
            "    return target in dp\n"
        ),
        "hidden_tests": "assert can_partition([1, 5, 11, 5]) == True\nassert can_partition([1, 2, 3, 5]) == False",
    })

    tasks.append({
        "id": "bench_dp_13_max_product_subarray",
        "category": "code",
        "domain": "dynamic_programming",
        "prompt": "Implement max_product(nums: list) -> int returning largest contiguous subarray product.",
        "reference_solution": (
            "def max_product(nums: list) -> int:\n"
            "    if not nums: return 0\n"
            "    max_prod = min_prod = res = nums[0]\n"
            "    for x in nums[1:]:\n"
            "        candidates = (x, max_prod * x, min_prod * x)\n"
            "        max_prod = max(candidates)\n"
            "        min_prod = min(candidates)\n"
            "        res = max(res, max_prod)\n"
            "    return res\n"
        ),
        "hidden_tests": "assert max_product([2, 3, -2, 4]) == 6\nassert max_product([-2, 0, -1]) == 0",
    })

    tasks.append({
        "id": "bench_dp_14_longest_common_subsequence",
        "category": "code",
        "domain": "dynamic_programming",
        "prompt": "Implement longest_common_subsequence(text1: str, text2: str) -> int returning length of LCS.",
        "reference_solution": (
            "def longest_common_subsequence(text1: str, text2: str) -> int:\n"
            "    m, n = len(text1), len(text2)\n"
            "    dp = [[0] * (n + 1) for _ in range(m + 1)]\n"
            "    for i in range(1, m + 1):\n"
            "        for j in range(1, n + 1):\n"
            "            if text1[i - 1] == text2[j - 1]: dp[i][j] = dp[i - 1][j - 1] + 1\n"
            "            else: dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])\n"
            "    return dp[m][n]\n"
        ),
        "hidden_tests": "assert longest_common_subsequence('abcde', 'ace') == 3\nassert longest_common_subsequence('abc', 'def') == 0",
    })

    tasks.append({
        "id": "bench_dp_15_jump_game",
        "category": "code",
        "domain": "dynamic_programming",
        "prompt": "Implement can_jump(nums: list) -> bool determining if last index can be reached from start.",
        "reference_solution": (
            "def can_jump(nums: list) -> bool:\n"
            "    max_reach = 0\n"
            "    for i, x in enumerate(nums):\n"
            "        if i > max_reach: return False\n"
            "        max_reach = max(max_reach, i + x)\n"
            "    return True\n"
        ),
        "hidden_tests": "assert can_jump([2, 3, 1, 1, 4]) == True\nassert can_jump([3, 2, 1, 0, 4]) == False",
    })

    tasks.append({
        "id": "bench_dp_16_target_sum",
        "category": "code",
        "domain": "dynamic_programming",
        "prompt": "Implement find_target_sum_ways(nums: list, target: int) -> int assigning '+' or '-' to reach target.",
        "reference_solution": (
            "def find_target_sum_ways(nums: list, target: int) -> int:\n"
            "    from collections import defaultdict\n"
            "    dp = defaultdict(int)\n"
            "    dp[0] = 1\n"
            "    for x in nums:\n"
            "        nxt = defaultdict(int)\n"
            "        for s, count in dp.items():\n"
            "            nxt[s + x] += count\n"
            "            nxt[s - x] += count\n"
            "        dp = nxt\n"
            "    return dp[target]\n"
        ),
        "hidden_tests": "assert find_target_sum_ways([1, 1, 1, 1, 1], 3) == 5\nassert find_target_sum_ways([1], 1) == 1",
    })

    tasks.append({
        "id": "bench_dp_17_coin_change_ways",
        "category": "code",
        "domain": "dynamic_programming",
        "prompt": "Implement change_ways(amount: int, coins: list) -> int returning number of combinations that make up amount.",
        "reference_solution": (
            "def change_ways(amount: int, coins: list) -> int:\n"
            "    dp = [0] * (amount + 1)\n"
            "    dp[0] = 1\n"
            "    for c in coins:\n"
            "        for x in range(c, amount + 1):\n"
            "            dp[x] += dp[x - c]\n"
            "    return dp[amount]\n"
        ),
        "hidden_tests": "assert change_ways(5, [1, 2, 5]) == 4\nassert change_ways(3, [2]) == 0",
    })

    tasks.append({
        "id": "bench_dp_18_combination_sum_4",
        "category": "code",
        "domain": "dynamic_programming",
        "prompt": "Implement combination_sum_4(nums: list, target: int) -> int returning number of possible permutations summing to target.",
        "reference_solution": (
            "def combination_sum_4(nums: list, target: int) -> int:\n"
            "    dp = [0] * (target + 1)\n"
            "    dp[0] = 1\n"
            "    for i in range(1, target + 1):\n"
            "        for x in nums:\n"
            "            if i - x >= 0: dp[i] += dp[i - x]\n"
            "    return dp[target]\n"
        ),
        "hidden_tests": "assert combination_sum_4([1, 2, 3], 4) == 7\nassert combination_sum_4([9], 3) == 0",
    })

    tasks.append({
        "id": "bench_dp_19_integer_break",
        "category": "code",
        "domain": "dynamic_programming",
        "prompt": "Implement integer_break(n: int) -> int breaking n into sum of k positive integers maximizing product.",
        "reference_solution": (
            "def integer_break(n: int) -> int:\n"
            "    if n <= 3: return n - 1\n"
            "    dp = [0] * (n + 1)\n"
            "    for i in range(1, 4): dp[i] = i\n"
            "    for i in range(4, n + 1):\n"
            "        dp[i] = max(2 * dp[i - 2], 3 * dp[i - 3])\n"
            "    return dp[n]\n"
        ),
        "hidden_tests": "assert integer_break(2) == 1\nassert integer_break(10) == 36",
    })

    tasks.append({
        "id": "bench_dp_20_pascals_triangle",
        "category": "code",
        "domain": "dynamic_programming",
        "prompt": "Implement generate_pascals(num_rows: int) -> list returning first num_rows of Pascal's triangle.",
        "reference_solution": (
            "def generate_pascals(num_rows: int) -> list:\n"
            "    res = []\n"
            "    for i in range(num_rows):\n"
            "        row = [1] * (i + 1)\n"
            "        for j in range(1, i):\n"
            "            row[j] = res[i - 1][j - 1] + res[i - 1][j]\n"
            "        res.append(row)\n"
            "    return res\n"
        ),
        "hidden_tests": "assert generate_pascals(5) == [[1], [1, 1], [1, 2, 1], [1, 3, 3, 1], [1, 4, 6, 4, 1]]\nassert generate_pascals(1) == [[1]]",
    })

    # =========================================================================
    # 6. MATH & NUMBER THEORY (20 problems)
    # =========================================================================
    tasks.append({
        "id": "bench_math_01_sieve_primes",
        "category": "code",
        "domain": "math_number_theory",
        "prompt": "Implement sieve_of_eratosthenes(n: int) -> list returning all primes less than or equal to n.",
        "reference_solution": (
            "def sieve_of_eratosthenes(n: int) -> list:\n"
            "    if n < 2: return []\n"
            "    is_prime = [True] * (n + 1)\n"
            "    is_prime[0] = is_prime[1] = False\n"
            "    for p in range(2, int(n**0.5) + 1):\n"
            "        if is_prime[p]:\n"
            "            for i in range(p * p, n + 1, p):\n"
            "                is_prime[i] = False\n"
            "    return [p for p in range(2, n + 1) if is_prime[p]]\n"
        ),
        "hidden_tests": "assert sieve_of_eratosthenes(10) == [2, 3, 5, 7]\nassert sieve_of_eratosthenes(2) == [2]\nassert sieve_of_eratosthenes(1) == []",
    })

    tasks.append({
        "id": "bench_math_02_gcd_lcm",
        "category": "code",
        "domain": "math_number_theory",
        "prompt": "Implement gcd_and_lcm(a: int, b: int) -> tuple returning (GCD, LCM) of a and b.",
        "reference_solution": (
            "def gcd_and_lcm(a: int, b: int) -> tuple:\n"
            "    import math\n"
            "    g = math.gcd(a, b)\n"
            "    l = abs(a * b) // g if g != 0 else 0\n"
            "    return (g, l)\n"
        ),
        "hidden_tests": "assert gcd_and_lcm(12, 18) == (6, 36)\nassert gcd_and_lcm(7, 5) == (1, 35)",
    })

    tasks.append({
        "id": "bench_math_03_pow_x_n",
        "category": "code",
        "domain": "math_number_theory",
        "prompt": "Implement my_pow(x: float, n: int) -> float calculating x raised to the power n in O(log n).",
        "reference_solution": (
            "def my_pow(x: float, n: int) -> float:\n"
            "    if n < 0:\n"
            "        x = 1.0 / x; n = -n\n"
            "    res = 1.0\n"
            "    while n > 0:\n"
            "        if n % 2 == 1: res *= x\n"
            "        x *= x\n"
            "        n //= 2\n"
            "    return round(res, 5)\n"
        ),
        "hidden_tests": "assert abs(my_pow(2.0, 10) - 1024.0) < 1e-4\nassert abs(my_pow(2.1, 3) - 9.261) < 1e-4\nassert abs(my_pow(2.0, -2) - 0.25) < 1e-4",
    })

    tasks.append({
        "id": "bench_math_04_is_power_of_two",
        "category": "code",
        "domain": "math_number_theory",
        "prompt": "Implement is_power_of_two(n: int) -> bool checking if integer is a power of two using bitwise operators.",
        "reference_solution": (
            "def is_power_of_two(n: int) -> bool:\n"
            "    return n > 0 and (n & (n - 1)) == 0\n"
        ),
        "hidden_tests": "assert is_power_of_two(1) == True\nassert is_power_of_two(16) == True\nassert is_power_of_two(3) == False\nassert is_power_of_two(0) == False",
    })

    tasks.append({
        "id": "bench_math_05_count_primes",
        "category": "code",
        "domain": "math_number_theory",
        "prompt": "Implement count_primes(n: int) -> int returning number of prime numbers strictly less than n.",
        "reference_solution": (
            "def count_primes(n: int) -> int:\n"
            "    if n <= 2: return 0\n"
            "    s = [True] * n\n"
            "    s[0] = s[1] = False\n"
            "    for i in range(2, int(n**0.5) + 1):\n"
            "        if s[i]:\n"
            "            s[i*i:n:i] = [False] * len(s[i*i:n:i])\n"
            "    return sum(s)\n"
        ),
        "hidden_tests": "assert count_primes(10) == 4\nassert count_primes(0) == 0\nassert count_primes(1) == 0",
    })

    tasks.append({
        "id": "bench_math_06_integer_sqrt",
        "category": "code",
        "domain": "math_number_theory",
        "prompt": "Implement my_sqrt(x: int) -> int returning integer square root rounded down.",
        "reference_solution": (
            "def my_sqrt(x: int) -> int:\n"
            "    if x < 2: return x\n"
            "    left, right = 1, x // 2\n"
            "    while left <= right:\n"
            "        mid = (left + right) // 2\n"
            "        if mid * mid <= x < (mid + 1) * (mid + 1):\n"
            "            return mid\n"
            "        elif mid * mid > x: right = mid - 1\n"
            "        else: left = mid + 1\n"
            "    return right\n"
        ),
        "hidden_tests": "assert my_sqrt(4) == 2\nassert my_sqrt(8) == 2\nassert my_sqrt(0) == 0",
    })

    tasks.append({
        "id": "bench_math_07_modular_exponentiation",
        "category": "code",
        "domain": "math_number_theory",
        "prompt": "Implement mod_pow(base: int, exp: int, mod: int) -> int computing (base ** exp) % mod.",
        "reference_solution": (
            "def mod_pow(base: int, exp: int, mod: int) -> int:\n"
            "    res = 1\n"
            "    base = base % mod\n"
            "    while exp > 0:\n"
            "        if exp % 2 == 1: res = (res * base) % mod\n"
            "        base = (base * base) % mod\n"
            "        exp //= 2\n"
            "    return res\n"
        ),
        "hidden_tests": "assert mod_pow(2, 10, 1000) == 24\nassert mod_pow(3, 7, 13) == 3\nassert mod_pow(5, 0, 7) == 1",
    })

    tasks.append({
        "id": "bench_math_08_trailing_zeroes_factorial",
        "category": "code",
        "domain": "math_number_theory",
        "prompt": "Implement trailing_zeroes(n: int) -> int returning number of trailing zeroes in n!.",
        "reference_solution": (
            "def trailing_zeroes(n: int) -> int:\n"
            "    count = 0\n"
            "    while n >= 5:\n"
            "        count += n // 5\n"
            "        n //= 5\n"
            "    return count\n"
        ),
        "hidden_tests": "assert trailing_zeroes(3) == 0\nassert trailing_zeroes(5) == 1\nassert trailing_zeroes(25) == 6",
    })

    tasks.append({
        "id": "bench_math_09_excel_column_number",
        "category": "code",
        "domain": "math_number_theory",
        "prompt": "Implement title_to_number(column_title: str) -> int converting Excel column title like 'AB' to number.",
        "reference_solution": (
            "def title_to_number(column_title: str) -> int:\n"
            "    res = 0\n"
            "    for c in column_title:\n"
            "        res = res * 26 + (ord(c) - ord('A') + 1)\n"
            "    return res\n"
        ),
        "hidden_tests": "assert title_to_number('A') == 1\nassert title_to_number('AB') == 28\nassert title_to_number('ZY') == 701",
    })

    tasks.append({
        "id": "bench_math_10_happy_number",
        "category": "code",
        "domain": "math_number_theory",
        "prompt": "Implement is_happy(n: int) -> bool checking if a number is happy (sum of squared digits reaches 1).",
        "reference_solution": (
            "def is_happy(n: int) -> bool:\n"
            "    seen = set()\n"
            "    while n != 1 and n not in seen:\n"
            "        seen.add(n)\n"
            "        n = sum(int(d)**2 for d in str(n))\n"
            "    return n == 1\n"
        ),
        "hidden_tests": "assert is_happy(19) == True\nassert is_happy(2) == False",
    })

    tasks.append({
        "id": "bench_math_11_add_digits_digital_root",
        "category": "code",
        "domain": "math_number_theory",
        "prompt": "Implement add_digits(num: int) -> int repeatedly adding all its digits until the result has one digit.",
        "reference_solution": (
            "def add_digits(num: int) -> int:\n"
            "    if num == 0: return 0\n"
            "    return 1 + (num - 1) % 9\n"
        ),
        "hidden_tests": "assert add_digits(38) == 2\nassert add_digits(0) == 0",
    })

    tasks.append({
        "id": "bench_math_12_valid_perfect_square",
        "category": "code",
        "domain": "math_number_theory",
        "prompt": "Implement is_perfect_square(num: int) -> bool returning True if num is a valid perfect square without built-in sqrt.",
        "reference_solution": (
            "def is_perfect_square(num: int) -> bool:\n"
            "    r = num\n"
            "    while r * r > num:\n"
            "        r = (r + num // r) // 2\n"
            "    return r * r == num\n"
        ),
        "hidden_tests": "assert is_perfect_square(16) == True\nassert is_perfect_square(14) == False\nassert is_perfect_square(1) == True",
    })

    tasks.append({
        "id": "bench_math_13_ugly_number",
        "category": "code",
        "domain": "math_number_theory",
        "prompt": "Implement is_ugly(n: int) -> bool checking if prime factors are limited to 2, 3, and 5.",
        "reference_solution": (
            "def is_ugly(n: int) -> bool:\n"
            "    if n <= 0: return False\n"
            "    for p in [2, 3, 5]:\n"
            "        while n % p == 0: n //= p\n"
            "    return n == 1\n"
        ),
        "hidden_tests": "assert is_ugly(6) == True\nassert is_ugly(1) == True\nassert is_ugly(14) == False",
    })

    tasks.append({
        "id": "bench_math_14_combinations_ncr",
        "category": "code",
        "domain": "math_number_theory",
        "prompt": "Implement nCr(n: int, r: int) -> int computing combination n choose r.",
        "reference_solution": (
            "def nCr(n: int, r: int) -> int:\n"
            "    import math\n"
            "    if r < 0 or r > n: return 0\n"
            "    return math.comb(n, r)\n"
        ),
        "hidden_tests": "assert nCr(5, 2) == 10\nassert nCr(10, 3) == 120\nassert nCr(4, 0) == 1",
    })

    tasks.append({
        "id": "bench_math_15_base_conversion",
        "category": "code",
        "domain": "math_number_theory",
        "prompt": "Implement to_binary_string(n: int) -> str returning binary representation of positive integer.",
        "reference_solution": (
            "def to_binary_string(n: int) -> str:\n"
            "    return bin(n)[2:]\n"
        ),
        "hidden_tests": "assert to_binary_string(5) == '101'\nassert to_binary_string(0) == '0'\nassert to_binary_string(15) == '1111'",
    })

    tasks.append({
        "id": "bench_math_16_fibonacci_fast",
        "category": "code",
        "domain": "math_number_theory",
        "prompt": "Implement fib_fast(n: int) -> int calculating nth Fibonacci number modulo 10**9 + 7.",
        "reference_solution": (
            "def fib_fast(n: int) -> int:\n"
            "    MOD = 10**9 + 7\n"
            "    if n <= 0: return 0\n"
            "    if n == 1: return 1\n"
            "    a, b = 0, 1\n"
            "    for _ in range(2, n + 1): a, b = b, (a + b) % MOD\n"
            "    return b\n"
        ),
        "hidden_tests": "assert fib_fast(10) == 55\nassert fib_fast(0) == 0\nassert fib_fast(50) == 586268941",
    })

    tasks.append({
        "id": "bench_math_17_collatz_steps",
        "category": "code",
        "domain": "math_number_theory",
        "prompt": "Implement collatz_steps(n: int) -> int returning number of steps to reach 1 in 3n+1 sequence.",
        "reference_solution": (
            "def collatz_steps(n: int) -> int:\n"
            "    steps = 0\n"
            "    while n > 1:\n"
            "        n = n // 2 if n % 2 == 0 else 3 * n + 1\n"
            "        steps += 1\n"
            "    return steps\n"
        ),
        "hidden_tests": "assert collatz_steps(1) == 0\nassert collatz_steps(6) == 8\nassert collatz_steps(11) == 14",
    })

    tasks.append({
        "id": "bench_math_18_sum_of_divisors",
        "category": "code",
        "domain": "math_number_theory",
        "prompt": "Implement sum_divisors(n: int) -> int returning sum of all proper divisors of n (excluding n).",
        "reference_solution": (
            "def sum_divisors(n: int) -> int:\n"
            "    if n <= 1: return 0\n"
            "    total = 1\n"
            "    for i in range(2, int(n**0.5) + 1):\n"
            "        if n % i == 0:\n"
            "            total += i\n"
            "            if i * i != n: total += n // i\n"
            "    return total\n"
        ),
        "hidden_tests": "assert sum_divisors(6) == 6\nassert sum_divisors(28) == 28\nassert sum_divisors(12) == 16",
    })

    tasks.append({
        "id": "bench_math_19_armstrong_number",
        "category": "code",
        "domain": "math_number_theory",
        "prompt": "Implement is_armstrong(n: int) -> bool checking if sum of its digits each raised to power of number of digits equals n.",
        "reference_solution": (
            "def is_armstrong(n: int) -> bool:\n"
            "    s = str(n)\n"
            "    k = len(s)\n"
            "    return sum(int(d)**k for d in s) == n\n"
        ),
        "hidden_tests": "assert is_armstrong(153) == True\nassert is_armstrong(370) == True\nassert is_armstrong(123) == False",
    })

    tasks.append({
        "id": "bench_math_20_matrix_multiplication",
        "category": "code",
        "domain": "math_number_theory",
        "prompt": "Implement matrix_mult(a: list, b: list) -> list multiplying two 2D matrices a and b.",
        "reference_solution": (
            "def matrix_mult(a: list, b: list) -> list:\n"
            "    rows_a, cols_a = len(a), len(a[0])\n"
            "    rows_b, cols_b = len(b), len(b[0])\n"
            "    res = [[0] * cols_b for _ in range(rows_a)]\n"
            "    for i in range(rows_a):\n"
            "        for j in range(cols_b):\n"
            "            res[i][j] = sum(a[i][k] * b[k][j] for k in range(cols_a))\n"
            "    return res\n"
        ),
        "hidden_tests": "a = [[1, 2], [3, 4]]\nb = [[5, 6], [7, 8]]\nassert matrix_mult(a, b) == [[19, 22], [43, 50]]",
    })

    # =========================================================================
    # 7. HASH MAPS & SETS (20 problems)
    # =========================================================================
    tasks.append({
        "id": "bench_hash_01_first_unique_char",
        "category": "code",
        "domain": "hash_maps_sets",
        "prompt": "Implement first_unique_char(s: str) -> int returning index of first non-repeating character in s or -1.",
        "reference_solution": (
            "def first_unique_char(s: str) -> int:\n"
            "    from collections import Counter\n"
            "    counts = Counter(s)\n"
            "    for i, c in enumerate(s):\n"
            "        if counts[c] == 1: return i\n"
            "    return -1\n"
        ),
        "hidden_tests": "assert first_unique_char('leetcode') == 0\nassert first_unique_char('loveleetcode') == 2\nassert first_unique_char('aabb') == -1",
    })

    tasks.append({
        "id": "bench_hash_02_contains_duplicate_nearby",
        "category": "code",
        "domain": "hash_maps_sets",
        "prompt": "Implement contains_nearby_duplicate(nums: list, k: int) -> bool checking if nums[i] == nums[j] and abs(i - j) <= k.",
        "reference_solution": (
            "def contains_nearby_duplicate(nums: list, k: int) -> bool:\n"
            "    seen = {}\n"
            "    for i, x in enumerate(nums):\n"
            "        if x in seen and i - seen[x] <= k: return True\n"
            "        seen[x] = i\n"
            "    return False\n"
        ),
        "hidden_tests": "assert contains_nearby_duplicate([1, 2, 3, 1], 3) == True\nassert contains_nearby_duplicate([1, 2, 3, 1, 2, 3], 2) == False",
    })

    tasks.append({
        "id": "bench_hash_03_subarray_sum_k",
        "category": "code",
        "domain": "hash_maps_sets",
        "prompt": "Implement subarray_sum(nums: list, k: int) -> int returning total number of subarrays whose sum equals k.",
        "reference_solution": (
            "def subarray_sum(nums: list, k: int) -> int:\n"
            "    from collections import defaultdict\n"
            "    counts = defaultdict(int)\n"
            "    counts[0] = 1\n"
            "    curr = 0; ans = 0\n"
            "    for x in nums:\n"
            "        curr += x\n"
            "        ans += counts[curr - k]\n"
            "        counts[curr] += 1\n"
            "    return ans\n"
        ),
        "hidden_tests": "assert subarray_sum([1, 1, 1], 2) == 2\nassert subarray_sum([1, 2, 3], 3) == 2",
    })

    tasks.append({
        "id": "bench_hash_04_top_k_frequent",
        "category": "code",
        "domain": "hash_maps_sets",
        "prompt": "Implement top_k_frequent(nums: list, k: int) -> list returning k most frequent elements sorted.",
        "reference_solution": (
            "def top_k_frequent(nums: list, k: int) -> list:\n"
            "    from collections import Counter\n"
            "    counts = Counter(nums)\n"
            "    return sorted([item for item, _ in counts.most_common(k)])\n"
        ),
        "hidden_tests": "assert top_k_frequent([1, 1, 1, 2, 2, 3], 2) == [1, 2]\nassert top_k_frequent([1], 1) == [1]",
    })

    tasks.append({
        "id": "bench_hash_05_longest_consecutive_sequence",
        "category": "code",
        "domain": "hash_maps_sets",
        "prompt": "Implement longest_consecutive(nums: list) -> int returning length of longest consecutive elements sequence in O(n).",
        "reference_solution": (
            "def longest_consecutive(nums: list) -> int:\n"
            "    num_set = set(nums)\n"
            "    best = 0\n"
            "    for x in num_set:\n"
            "        if x - 1 not in num_set:\n"
            "            y = x + 1\n"
            "            while y in num_set: y += 1\n"
            "            best = max(best, y - x)\n"
            "    return best\n"
        ),
        "hidden_tests": "assert longest_consecutive([100, 4, 200, 1, 3, 2]) == 4\nassert longest_consecutive([0, 3, 7, 2, 5, 8, 4, 6, 0, 1]) == 9",
    })

    tasks.append({
        "id": "bench_hash_06_ransom_note",
        "category": "code",
        "domain": "hash_maps_sets",
        "prompt": "Implement can_construct(ransom_note: str, magazine: str) -> bool checking if ransom_note can be built from magazine letters.",
        "reference_solution": (
            "def can_construct(ransom_note: str, magazine: str) -> bool:\n"
            "    from collections import Counter\n"
            "    r_cnt = Counter(ransom_note)\n"
            "    m_cnt = Counter(magazine)\n"
            "    return all(m_cnt[c] >= count for c, count in r_cnt.items())\n"
        ),
        "hidden_tests": "assert can_construct('a', 'b') == False\nassert can_construct('aa', 'ab') == False\nassert can_construct('aa', 'aab') == True",
    })

    tasks.append({
        "id": "bench_hash_07_find_words_by_chars",
        "category": "code",
        "domain": "hash_maps_sets",
        "prompt": "Implement count_characters(words: list, chars: str) -> int returning sum of lengths of words formed by chars.",
        "reference_solution": (
            "def count_characters(words: list, chars: str) -> int:\n"
            "    from collections import Counter\n"
            "    c_cnt = Counter(chars)\n"
            "    total = 0\n"
            "    for w in words:\n"
            "        w_cnt = Counter(w)\n"
            "        if all(c_cnt[c] >= cnt for c, cnt in w_cnt.items()): total += len(w)\n"
            "    return total\n"
        ),
        "hidden_tests": "assert count_characters(['cat', 'bt', 'hat', 'tree'], 'atach') == 6",
    })

    tasks.append({
        "id": "bench_hash_08_bulls_and_cows",
        "category": "code",
        "domain": "hash_maps_sets",
        "prompt": "Implement get_hint(secret: str, guess: str) -> str returning hint formatted as 'xAyB'.",
        "reference_solution": (
            "def get_hint(secret: str, guess: str) -> str:\n"
            "    from collections import Counter\n"
            "    bulls = sum(s == g for s, g in zip(secret, guess))\n"
            "    s_cnt = Counter(secret)\n"
            "    g_cnt = Counter(guess)\n"
            "    cows = sum(min(s_cnt[c], g_cnt[c]) for c in s_cnt) - bulls\n"
            "    return f'{bulls}A{cows}B'\n"
        ),
        "hidden_tests": "assert get_hint('1807', '7810') == '1A3B'\nassert get_hint('1123', '0111') == '1A1B'",
    })

    tasks.append({
        "id": "bench_hash_09_jewels_and_stones",
        "category": "code",
        "domain": "hash_maps_sets",
        "prompt": "Implement num_jewels_in_stones(jewels: str, stones: str) -> int counting stones that are also jewels.",
        "reference_solution": (
            "def num_jewels_in_stones(jewels: str, stones: str) -> int:\n"
            "    j_set = set(jewels)\n"
            "    return sum(1 for s in stones if s in j_set)\n"
        ),
        "hidden_tests": "assert num_jewels_in_stones('aA', 'aAAbbbb') == 3\nassert num_jewels_in_stones('z', 'ZZ') == 0",
    })

    tasks.append({
        "id": "bench_hash_10_unique_email_addresses",
        "category": "code",
        "domain": "hash_maps_sets",
        "prompt": "Implement num_unique_emails(emails: list) -> int counting distinct canonical emails after cleaning '.' and '+'.",
        "reference_solution": (
            "def num_unique_emails(emails: list) -> int:\n"
            "    seen = set()\n"
            "    for email in emails:\n"
            "        local, domain = email.split('@')\n"
            "        local = local.split('+')[0].replace('.', '')\n"
            "        seen.add(f'{local}@{domain}')\n"
            "    return len(seen)\n"
        ),
        "hidden_tests": "emails = ['test.email+alex@leetcode.com', 'test.e.mail+bob.cathy@leetcode.com', 'testemail+david@lee.tcode.com']\nassert num_unique_emails(emails) == 2",
    })

    tasks.append({
        "id": "bench_hash_11_destination_city",
        "category": "code",
        "domain": "hash_maps_sets",
        "prompt": "Implement dest_city(paths: list) -> str finding the city without any outgoing path.",
        "reference_solution": (
            "def dest_city(paths: list) -> str:\n"
            "    outgoing = {p[0] for p in paths}\n"
            "    for _, dst in paths:\n"
            "        if dst not in outgoing: return dst\n"
            "    return ''\n"
        ),
        "hidden_tests": "assert dest_city([['London', 'New York'], ['New York', 'Lima'], ['Lima', 'Sao Paulo']]) == 'Sao Paulo'\nassert dest_city([['B', 'C'], ['D', 'B'], ['C', 'A']]) == 'A'",
    })

    tasks.append({
        "id": "bench_hash_12_sort_characters_frequency",
        "category": "code",
        "domain": "hash_maps_sets",
        "prompt": "Implement frequency_sort(s: str) -> str sorting string characters in decreasing order of frequency.",
        "reference_solution": (
            "def frequency_sort(s: str) -> str:\n"
            "    from collections import Counter\n"
            "    counts = Counter(s)\n"
            "    return ''.join(c * cnt for c, cnt in counts.most_common())\n"
        ),
        "hidden_tests": "res = frequency_sort('tree')\nassert res in ('eert', 'eetr')",
    })

    tasks.append({
        "id": "bench_hash_13_contiguous_array_equal_zero_one",
        "category": "code",
        "domain": "hash_maps_sets",
        "prompt": "Implement find_max_length(nums: list) -> int finding max length of contiguous subarray with equal 0 and 1.",
        "reference_solution": (
            "def find_max_length(nums: list) -> int:\n"
            "    seen = {0: -1}\n"
            "    curr = 0; max_len = 0\n"
            "    for i, x in enumerate(nums):\n"
            "        curr += (1 if x == 1 else -1)\n"
            "        if curr in seen: max_len = max(max_len, i - seen[curr])\n"
            "        else: seen[curr] = i\n"
            "    return max_len\n"
        ),
        "hidden_tests": "assert find_max_length([0, 1]) == 2\nassert find_max_length([0, 1, 0]) == 2",
    })

    tasks.append({
        "id": "bench_hash_14_single_number",
        "category": "code",
        "domain": "hash_maps_sets",
        "prompt": "Implement single_number(nums: list) -> int finding the only element appearing once using XOR.",
        "reference_solution": (
            "def single_number(nums: list) -> int:\n"
            "    res = 0\n"
            "    for x in nums: res ^= x\n"
            "    return res\n"
        ),
        "hidden_tests": "assert single_number([2, 2, 1]) == 1\nassert single_number([4, 1, 2, 1, 2]) == 4",
    })

    tasks.append({
        "id": "bench_hash_15_distribute_candies",
        "category": "code",
        "domain": "hash_maps_sets",
        "prompt": "Implement distribute_candies(candy_type: list) -> int returning max types of candy a person can eat eating n//2 candies.",
        "reference_solution": (
            "def distribute_candies(candy_type: list) -> int:\n"
            "    return min(len(set(candy_type)), len(candy_type) // 2)\n"
        ),
        "hidden_tests": "assert distribute_candies([1, 1, 2, 2, 3, 3]) == 3\nassert distribute_candies([1, 1, 2, 3]) == 2",
    })

    tasks.append({
        "id": "bench_hash_16_keyboard_row",
        "category": "code",
        "domain": "hash_maps_sets",
        "prompt": "Implement find_words_keyboard(words: list) -> list returning words that can be typed using letters of one keyboard row.",
        "reference_solution": (
            "def find_words_keyboard(words: list) -> list:\n"
            "    r1, r2, r3 = set('qwertyuiop'), set('asdfghjkl'), set('zxcvbnm')\n"
            "    res = []\n"
            "    for w in words:\n"
            "        low = set(w.lower())\n"
            "        if low <= r1 or low <= r2 or low <= r3: res.append(w)\n"
            "    return res\n"
        ),
        "hidden_tests": "assert find_words_keyboard(['Hello', 'Alaska', 'Dad', 'Peace']) == ['Alaska', 'Dad']\nassert find_words_keyboard(['omk']) == []",
    })

    tasks.append({
        "id": "bench_hash_17_unique_occurrences",
        "category": "code",
        "domain": "hash_maps_sets",
        "prompt": "Implement unique_occurrences(arr: list) -> bool returning True if the number of occurrences of each value in arr is unique.",
        "reference_solution": (
            "def unique_occurrences(arr: list) -> bool:\n"
            "    from collections import Counter\n"
            "    counts = Counter(arr).values()\n"
            "    return len(counts) == len(set(counts))\n"
        ),
        "hidden_tests": "assert unique_occurrences([1, 2, 2, 1, 1, 3]) == True\nassert unique_occurrences([1, 2]) == False",
    })

    tasks.append({
        "id": "bench_hash_18_check_if_pangram",
        "category": "code",
        "domain": "hash_maps_sets",
        "prompt": "Implement check_if_pangram(sentence: str) -> bool returning True if sentence contains every letter of the English alphabet.",
        "reference_solution": (
            "def check_if_pangram(sentence: str) -> bool:\n"
            "    return len(set(c for c in sentence.lower() if 'a' <= c <= 'z')) == 26\n"
        ),
        "hidden_tests": "assert check_if_pangram('thequickbrownfoxjumpsoverthelazydog') == True\nassert check_if_pangram('leetcode') == False",
    })

    tasks.append({
        "id": "bench_hash_19_rings_and_rods",
        "category": "code",
        "domain": "hash_maps_sets",
        "prompt": "Implement count_points_rods(rings: str) -> int counting rods that hold all three colors 'R', 'G', 'B'.",
        "reference_solution": (
            "def count_points_rods(rings: str) -> int:\n"
            "    from collections import defaultdict\n"
            "    rods = defaultdict(set)\n"
            "    for i in range(0, len(rings), 2):\n"
            "        color, rod = rings[i], rings[i + 1]\n"
            "        rods[rod].add(color)\n"
            "    return sum(1 for colors in rods.values() if len(colors) == 3)\n"
        ),
        "hidden_tests": "assert count_points_rods('B0R0G0R9R0B0G0') == 1\nassert count_points_rods('G4') == 0",
    })

    tasks.append({
        "id": "bench_hash_20_lru_cache_logic",
        "category": "code",
        "domain": "hash_maps_sets",
        "prompt": "Implement LRUCache class supporting get(key) and put(key, value) with capacity constraint in O(1).",
        "reference_solution": (
            "from collections import OrderedDict\n"
            "class LRUCache:\n"
            "    def __init__(self, capacity: int):\n"
            "        self.cap = capacity\n"
            "        self.cache = OrderedDict()\n"
            "    def get(self, key: int) -> int:\n"
            "        if key not in self.cache: return -1\n"
            "        self.cache.move_to_end(key)\n"
            "        return self.cache[key]\n"
            "    def put(self, key: int, value: int) -> None:\n"
            "        if key in self.cache: self.cache.move_to_end(key)\n"
            "        self.cache[key] = value\n"
            "        if len(self.cache) > self.cap: self.cache.popitem(last=False)\n"
        ),
        "hidden_tests": "lru = LRUCache(2)\nlru.put(1, 1); lru.put(2, 2)\nassert lru.get(1) == 1\nlru.put(3, 3)\nassert lru.get(2) == -1",
    })

    # =========================================================================
    # 8. SCHEMA & PROTOCOL CONTRACTS (20 problems)
    # =========================================================================
    schema_specs = [
        ("01_p2p_ping", "p2p node ping", ["node_id", "peer_pubkey", "timestamp", "protocol_version"], '{"node_id": "node-alpha", "peer_pubkey": "ed25519-abc", "timestamp": 1700000000, "protocol_version": "v2.4"}'),
        ("02_worker_lease", "worker job lease", ["job_id", "worker_id", "lease_token", "expires_at", "credits"], '{"job_id": "job-101", "worker_id": "w-7", "lease_token": "tok-99", "expires_at": 1700003600, "credits": 50}'),
        ("03_escrow_contract", "escrow payment", ["contract_id", "buyer", "seller", "amount_credits", "status"], '{"contract_id": "esc-1", "buyer": "alice", "seller": "bob", "amount_credits": 250, "status": "LOCKED"}'),
        ("04_telemetry_metric", "cluster telemetry", ["metric_name", "value", "unit", "host", "collected_at"], '{"metric_name": "cpu_utilization", "value": 42.5, "unit": "percent", "host": "srv-01", "collected_at": 1700000100}'),
        ("05_consensus_vote", "consensus vote", ["round_id", "proposer", "vote_choice", "voter_signature"], '{"round_id": 42, "proposer": "validator-1", "vote_choice": "APPROVE", "voter_signature": "sig-0x88"}'),
        ("06_block_header", "hash chain block header", ["block_index", "previous_hash", "merkle_root", "timestamp", "nonce"], '{"block_index": 12, "previous_hash": "0000abcd", "merkle_root": "efff1234", "timestamp": 1700001200, "nonce": 4242}'),
        ("07_token_budget", "token budget quota", ["user_id", "tier", "allocated_tokens", "used_tokens", "remaining_tokens"], '{"user_id": "usr-9", "tier": "PRO", "allocated_tokens": 100000, "used_tokens": 1250, "remaining_tokens": 98750}'),
        ("08_exec_result", "sandbox exec result", ["execution_id", "exit_code", "stdout", "stderr", "duration_seconds"], '{"execution_id": "exec-5", "exit_code": 0, "stdout": "Success", "stderr": "", "duration_seconds": 0.045}'),
        ("09_error_report", "mesh error log", ["error_code", "component", "message", "severity", "stack_trace_hash"], '{"error_code": "ERR_ROUTER_FAILOVER", "component": "router", "message": "Primary node timeout", "severity": "WARN", "stack_trace_hash": "hash-991"}'),
        ("10_credential_meta", "credential record", ["key_id", "algorithm", "created_by", "expires_epoch", "is_revoked"], '{"key_id": "key-33", "algorithm": "Ed25519", "created_by": "root", "expires_epoch": 1705000000, "is_revoked": false}'),
        ("11_mesh_route", "route broadcast", ["target_model", "gateway_url", "priority", "estimated_latency_ms"], '{"target_model": "llama3.1:8b", "gateway_url": "http://127.0.0.1:11434", "priority": 1, "estimated_latency_ms": 120}'),
        ("12_health_ping", "node heartbeat", ["node_id", "health_status", "uptime_hours", "active_tasks"], '{"node_id": "node-beta", "health_status": "HEALTHY", "uptime_hours": 72.5, "active_tasks": 3}'),
        ("13_file_replication", "file chunk transfer", ["file_hash", "chunk_index", "total_chunks", "chunk_size_bytes"], '{"file_hash": "sha256-abcdef", "chunk_index": 2, "total_chunks": 10, "chunk_size_bytes": 65536}'),
        ("14_resource_quote", "resource quotation", ["provider_id", "gpu_type", "vram_gb", "price_per_hour_credits"], '{"provider_id": "prov-4", "gpu_type": "NVIDIA_RTX_4090", "vram_gb": 24, "price_per_hour_credits": 15}'),
        ("15_audit_log", "compliance audit log", ["audit_id", "action_name", "operator", "target_resource", "compliance_pass"], '{"audit_id": "aud-109", "action_name": "ROTATE_ROOT_SECRETS", "operator": "sec-officer", "target_resource": "vault", "compliance_pass": true}'),
        ("16_sandbox_spec", "sandbox container spec", ["container_id", "memory_limit_mb", "cpu_shares", "network_isolated"], '{"container_id": "box-77", "memory_limit_mb": 512, "cpu_shares": 1024, "network_isolated": true}'),
        ("17_model_card", "fine-tuned model card", ["model_name", "base_checkpoint", "adapter_format", "parameters_millions"], '{"model_name": "nexus-qlora-8b", "base_checkpoint": "llama3.1:8b", "adapter_format": "safetensors", "parameters_millions": 8030}'),
        ("18_benchmark_report", "benchmark test run", ["benchmark_id", "total_tasks", "pass_rate", "average_loss", "execution_time_s"], '{"benchmark_id": "run-404", "total_tasks": 160, "pass_rate": 0.9875, "average_loss": 0.0124, "execution_time_s": 14.2}'),
        ("19_ota_manifest", "signed OTA release", ["version", "build_hash", "signer_pubkey", "signature", "mandatory"], '{"version": "2026.4.1", "build_hash": "build-a1b2", "signer_pubkey": "pub-ota-root", "signature": "sig-ed25519", "mandatory": true}'),
        ("20_worker_profile", "worker capability profile", ["worker_id", "supported_runtimes", "max_concurrent_jobs", "benchmark_tier"], '{"worker_id": "w-pro-1", "supported_runtimes": ["python3.10", "rust"], "max_concurrent_jobs": 8, "benchmark_tier": "TIER_A"}'),
    ]

    for sid, desc, keys, raw_json in schema_specs:
        tasks.append({
            "id": f"bench_schema_{sid}",
            "category": "schema",
            "domain": "schema_contracts",
            "prompt": f"Generate JSON record for {desc} with required fields: {', '.join(keys)}",
            "reference_solution": raw_json,
            "raw_json": raw_json,
            "required_keys": keys,
            "hidden_tests": json.dumps({"required_keys": keys}),
        })

    return tasks


class HeldOutBenchmarkManager:
    """Manages the standardized held-out benchmark battery stored outside git in data/benchmarks/."""

    def __init__(self, benchmark_dir: Optional[Path] = None):
        self.benchmark_dir = Path(benchmark_dir) if benchmark_dir else Path("data/benchmarks")
        self.battery_file = self.benchmark_dir / "held_out_evaluation_battery.jsonl"
        self._tasks: Optional[List[Dict[str, Any]]] = None

    def ensure_battery_on_disk(self) -> Path:
        """Ensures the 160 diverse problems are written to data/benchmarks/held_out_evaluation_battery.jsonl."""
        self.benchmark_dir.mkdir(parents=True, exist_ok=True)
        if not self.battery_file.exists() or self.battery_file.stat().st_size == 0:
            corpus = build_benchmark_corpus()
            with self.battery_file.open("w", encoding="utf-8") as fh:
                for task in corpus:
                    fh.write(json.dumps(task) + "\n")
                    fh.flush()
        return self.battery_file

    def load_tasks(self, force_reload: bool = False) -> List[Dict[str, Any]]:
        """Loads benchmark tasks from disk battery with lazy loading."""
        if self._tasks is not None and not force_reload:
            return list(self._tasks)

        self.ensure_battery_on_disk()
        tasks = []
        with self.battery_file.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        tasks.append(json.loads(line))
                    except Exception:
                        pass
        self._tasks = tasks
        return list(self._tasks)

    def get_tasks(
        self,
        domain: Optional[str] = None,
        category: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Returns filtered benchmark tasks."""
        all_tasks = self.load_tasks()
        filtered = all_tasks
        if domain:
            filtered = [t for t in filtered if t.get("domain") == domain]
        if category:
            filtered = [t for t in filtered if t.get("category") == category]
        if limit is not None and limit > 0:
            filtered = filtered[:limit]
        return filtered

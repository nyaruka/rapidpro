#!/bin/bash

#!/bin/bash

# Extract coverage percentage from lcov.info
COVERAGE=$(awk '
/^LH:/ { 
    hit += substr($0, 4) 
}
/^LF:/ { 
    total += substr($0, 4) 
}
END { 
    if(total > 0) 
        printf "%.1f", (hit/total)*100
    else 
        printf "0" 
}' coverage/lcov.info)

# Use bc for floating point comparison if available, otherwise use basic comparison
if command -v bc >/dev/null 2>&1; then
    if (( $(echo "$COVERAGE >= 95" | bc -l) )); then
        COLOR="limegreen"
    elif (( $(echo "$COVERAGE >= 80" | bc -l) )); then
        COLOR="orange"
    elif (( $(echo "$COVERAGE >= 60" | bc -l) )); then
        COLOR="tomato"
    else
        COLOR="red"
    fi
else
    # Fallback without bc
    COVERAGE_INT=${COVERAGE%.*}
    if [ "$COVERAGE_INT" -ge 95 ]; then
        COLOR="limegreen"
    elif [ "$COVERAGE_INT" -ge 80 ]; then
        COLOR="orange"
    elif [ "$COVERAGE_INT" -ge 60 ]; then
        COLOR="tomato"
    else
        COLOR="red"
    fi
fi

# Create SVG badge
cat > coverage/coverage-badge.svg << EOF
<svg xmlns="http://www.w3.org/2000/svg" width="104" height="20">
    <linearGradient id="b" x2="0" y2="100%">
        <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
        <stop offset="1" stop-opacity=".1"/>
    </linearGradient>
    <mask id="a">
        <rect width="104" height="20" rx="3" fill="#fff"/>
    </mask>
    <g mask="url(#a)">
        <path fill="#555" d="M0 0h63v20H0z"/>
        <path fill="${COLOR}" d="M63 0h41v20H63z"/>
        <path fill="url(#b)" d="M0 0h104v20H0z"/>
    </g>
    <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
        <text x="31.5" y="15" fill="#010101" fill-opacity=".3">coverage</text>
        <text x="31.5" y="14">coverage</text>
        <text x="83.5" y="15" fill="#010101" fill-opacity=".3">${COVERAGE}%</text>
        <text x="83.5" y="14">${COVERAGE}%</text>
    </g>
</svg>
EOF

echo "Coverage badge generated with ${COVERAGE}% coverage"
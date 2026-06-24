const state = {
  data: null,
  query: "",
  category: "",
  selectedCourse: "",
  sort: "course",
  visibleResources: 80,
};

const els = {
  search: document.querySelector("#search-input"),
  category: document.querySelector("#category-filter"),
  sort: document.querySelector("#sort-select"),
  clear: document.querySelector("#clear-button"),
  more: document.querySelector("#more-button"),
  courseCount: document.querySelector("#course-count"),
  resourceCount: document.querySelector("#resource-count"),
  visibleCount: document.querySelector("#visible-count"),
  resultSummary: document.querySelector("#result-summary"),
  courseList: document.querySelector("#course-list"),
  resourceList: document.querySelector("#resource-list"),
};

async function start() {
  const response = await fetch("data/resources.json");
  if (!response.ok) {
    throw new Error(`Unable to load index: ${response.status}`);
  }
  state.data = await response.json();
  populateCategories();
  bindEvents();
  render();
}

function populateCategories() {
  for (const category of state.data.categories) {
    const option = document.createElement("option");
    option.value = category;
    option.textContent = category;
    els.category.appendChild(option);
  }
}

function bindEvents() {
  els.search.addEventListener("input", () => {
    state.query = els.search.value.trim();
    state.visibleResources = 80;
    render();
  });
  els.category.addEventListener("change", () => {
    state.category = els.category.value;
    state.visibleResources = 80;
    render();
  });
  els.sort.addEventListener("change", () => {
    state.sort = els.sort.value;
    render();
  });
  els.clear.addEventListener("click", () => {
    state.query = "";
    state.category = "";
    state.selectedCourse = "";
    state.sort = "course";
    state.visibleResources = 80;
    els.search.value = "";
    els.category.value = "";
    els.sort.value = "course";
    render();
  });
  els.more.addEventListener("click", () => {
    state.visibleResources += 80;
    render();
  });
}

function render() {
  const resources = filteredResources();
  const courses = matchedCourses(resources);
  els.courseCount.textContent = state.data.course_count;
  els.resourceCount.textContent = state.data.resource_count;
  els.visibleCount.textContent = resources.length;
  els.resultSummary.textContent = summaryText(resources);
  renderCourses(courses);
  renderResources(resources);
}

function filteredResources() {
  const tokens = normalize(state.query).split(/\s+/).filter(Boolean);
  return state.data.resources.filter((resource) => {
    if (state.category && resource.category !== state.category) {
      return false;
    }
    if (state.selectedCourse && resource.course !== state.selectedCourse) {
      return false;
    }
    if (!tokens.length) {
      return true;
    }
    const haystack = normalize([
      resource.course,
      resource.category,
      resource.name,
      resource.source,
      resource.author,
      resource.file_type,
      resource.updated_at,
      resource.remark,
    ].join(" "));
    return tokens.every((token) => haystack.includes(token));
  }).sort(compareResources);
}

function compareResources(a, b) {
  if (state.sort === "resource") {
    return courseResourceCount(b.course) - courseResourceCount(a.course) || a.course.localeCompare(b.course, "zh-Hans-CN");
  }
  if (state.sort === "match") {
    return scoreResource(b) - scoreResource(a) || a.name.localeCompare(b.name, "zh-Hans-CN");
  }
  return a.course.localeCompare(b.course, "zh-Hans-CN") || a.category.localeCompare(b.category, "zh-Hans-CN") || a.name.localeCompare(b.name, "zh-Hans-CN");
}

function scoreResource(resource) {
  const query = normalize(state.query);
  if (!query) {
    return 0;
  }
  let score = 0;
  if (normalize(resource.course).includes(query)) score += 5;
  if (normalize(resource.name).includes(query)) score += 4;
  if (normalize(resource.remark).includes(query)) score += 1;
  return score;
}

function matchedCourses(resources) {
  const countByCourse = new Map();
  for (const resource of resources) {
    countByCourse.set(resource.course, (countByCourse.get(resource.course) || 0) + 1);
  }
  return state.data.courses
    .filter((course) => countByCourse.has(course.name))
    .map((course) => ({ ...course, visible_count: countByCourse.get(course.name) }))
    .sort((a, b) => {
      if (state.sort === "resource") {
        return b.visible_count - a.visible_count || a.name.localeCompare(b.name, "zh-Hans-CN");
      }
      return a.name.localeCompare(b.name, "zh-Hans-CN");
    });
}

function courseResourceCount(courseName) {
  const course = state.data.courses.find((item) => item.name === courseName);
  return course ? course.resource_count : 0;
}

function renderCourses(courses) {
  els.courseList.replaceChildren();
  if (!courses.length) {
    els.courseList.append(emptyNode("没有匹配课程"));
    return;
  }
  for (const course of courses.slice(0, 120)) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `course-card${course.name === state.selectedCourse ? " active" : ""}`;
    button.addEventListener("click", () => {
      state.selectedCourse = state.selectedCourse === course.name ? "" : course.name;
      state.visibleResources = 80;
      render();
    });
    button.innerHTML = `
      <div class="course-title">${escapeHtml(course.name)}</div>
      <div class="course-meta">
        <span>${course.visible_count} 条匹配</span>
        <span>${course.resource_count} 条总资源</span>
      </div>
    `;
    els.courseList.append(button);
  }
}

function renderResources(resources) {
  els.resourceList.replaceChildren();
  if (!resources.length) {
    els.resourceList.append(emptyNode("没有找到匹配资源。可以换一个课程名、年份或关键词。"));
    els.more.classList.remove("visible");
    return;
  }
  for (const resource of resources.slice(0, state.visibleResources)) {
    els.resourceList.append(resourceCard(resource));
  }
  els.more.classList.toggle("visible", resources.length > state.visibleResources);
}

function resourceCard(resource) {
  const article = document.createElement("article");
  article.className = "resource-card";
  article.dataset.category = resource.category;
  const meta = [
    resource.category,
    resource.file_type,
    resource.file_size,
    resource.source,
    resource.updated_at,
  ].filter(Boolean);
  article.innerHTML = `
    <div class="resource-main">
      <div>
        <div class="resource-title">${escapeHtml(resource.name)}</div>
        <div class="resource-meta">
          <span class="tag">${escapeHtml(resource.course)}</span>
          ${meta.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}
        </div>
      </div>
      <div class="resource-actions">
        <a href="${escapeAttribute(resource.url)}" target="_blank" rel="noreferrer">查看</a>
      </div>
    </div>
    ${resource.remark ? `<div class="resource-meta">${escapeHtml(resource.remark)}</div>` : ""}
  `;
  return article;
}

function emptyNode(text) {
  const div = document.createElement("div");
  div.className = "empty";
  div.textContent = text;
  return div;
}

function summaryText(resources) {
  if (state.selectedCourse) {
    return `${state.selectedCourse}，${resources.length} 条资源`;
  }
  return `${resources.length} 条资源`;
}

function normalize(value) {
  return String(value || "").toLocaleLowerCase("zh-Hans-CN").replace(/[^\p{L}\p{N}]+/gu, " ").trim();
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttribute(value) {
  return escapeHtml(value).replaceAll("`", "&#096;");
}

start().catch((error) => {
  els.resourceList.replaceChildren(emptyNode(error.message));
});
